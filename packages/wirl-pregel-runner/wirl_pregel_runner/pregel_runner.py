# Runner for Wirl workflows

from __future__ import annotations

import argparse
import json
import logging
import traceback
from typing import Any, Dict, List

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from wirl_pregel_runner.pregel_graph_builder import build_pregel_graph

logger = logging.getLogger(__name__)


def run_workflow(
    workflow_path: str,
    fn_map: Dict[str, Any],
    params: Dict[str, Any] | None = None,
    thread_id: str | None = None,
    resume: str | None = None,
    checkpointer: Any | None = None,
):
    logger.info(f"Running workflow {workflow_path} for thread {thread_id}, with params {params}, resume {resume}")
    app = build_pregel_graph(workflow_path, functions=fn_map, checkpointer=checkpointer)
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}, "recursion_limit": 1000}
    if resume:
        resume_val = json.loads(resume)
        config["configurable"]["resume"] = resume_val
        try:
            result = app.invoke(Command(resume=resume_val), config)
        except Exception as e:
            stack_trace = traceback.format_exc()
            logger.error(f"Error resuming workflow {workflow_path} for thread {thread_id}: {e}\n{stack_trace}")
            raise e
    else:
        result = app.invoke(params, config)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run an Wirl workflow.")
    parser.add_argument("workflow_path", type=str, help="Path to the workflow file")
    parser.add_argument("--functions", type=str, default="steps.deepresearch_functions", help="Python module containing the workflow functions")
    parser.add_argument("--param", action="append", default=[], help="Workflow input parameter key=value")
    parser.add_argument("--thread-id", type=str, default="cli")
    parser.add_argument("--resume", type=str, default=None)
    args = parser.parse_args()

    mod = __import__(args.functions, fromlist=["*"])
    fn_map = {k: getattr(mod, k) for k in dir(mod) if not k.startswith("_")}

    def parse_params(param_list: List[str]):
        out = {}
        for p in param_list:
            if "=" not in p:
                raise ValueError(f"Invalid param: {p}")
            k, v = p.split("=", 1)

            # Try to parse as JSON first (handles lists, dicts, booleans, null)
            if v.startswith(("[", "{")) or v in ("true", "false", "null"):
                try:
                    v = json.loads(v)
                except json.JSONDecodeError:
                    pass  # Fall through to other parsing methods
            # Try integer parsing
            elif v.isdigit():
                v = int(v)
            # Try float parsing
            else:
                try:
                    v = float(v)
                except ValueError:
                    pass  # Keep as string

            out[k] = v
        return out

    params = parse_params(args.param)
    result = run_workflow(args.workflow_path, fn_map, params, args.thread_id, args.resume)
