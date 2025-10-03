import asyncio
import json
import logging
import os
from typing import Any, Dict

import asyncpg
from langgraph.checkpoint.postgres import PostgresSaver
from wirl_pregel_runner import run_workflow

from workers.workflow_loader import get_template

logger = logging.getLogger(__name__)


async def claim_job(pool: asyncpg.pool.Pool, worker_id: str) -> Dict[str, Any] | None:
    async with pool.acquire() as conn, conn.transaction():
        row = await conn.fetchrow(
            """
            WITH next AS (
                SELECT id
                FROM workflow_runs
                WHERE state = 'queued'
                ORDER BY id
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            UPDATE workflow_runs
            SET state='running',
                worker_id = $1,
                started_at = now(),
                heartbeat_at = now(),
                attempt = attempt + 1
            FROM next
            WHERE workflow_runs.id = next.id
            RETURNING workflow_runs.*;
            """,
            worker_id,
        )
    return dict(row) if row else None


async def set_state(
    pool: asyncpg.pool.Pool,
    job_id: str,
    new_state: str,
    result: Dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    async with pool.acquire() as conn:
        try:
            res_str = json.dumps(result) if result is not None else "{}"
        except Exception as _:
            res_str = "{}"

        await conn.execute(
            """
            UPDATE workflow_runs
            SET state = $2::VARCHAR,
                heartbeat_at = CASE WHEN $2::VARCHAR='running' THEN now() ELSE heartbeat_at END,
                finished_at = CASE WHEN $2::VARCHAR IN ('succeeded','failed','canceled') THEN now() END,
                error = $3,
                result = COALESCE($4, result)
            WHERE id = $1 AND state != 'canceled'
            """,
            job_id,
            new_state,
            error,
            res_str,
        )


async def run_wirl(job: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
    tpl = get_template(job["graph_name"])
    if not tpl:
        raise ValueError("Template not found")
    params = json.loads(job.get("inputs", "{}"))
    resume = job.get("resume_payload")
    # Resume after interrupt or after continue failed job
    if resume or job.get("attempt", 0) > 1:
        params = None
        logger.info(f"Resuming job {job['id']} with params {params}")
    # Convert absolute path to relative module path
    workflow_path = tpl["path"]

    rel_path = os.path.relpath(workflow_path, start=os.getcwd())
    functions_module = rel_path.replace(".wirl", "").replace(os.sep, ".")

    mod = __import__(functions_module, fromlist=["*"])
    fn_map = {k: getattr(mod, k) for k in dir(mod) if not k.startswith("_")}
    db_url = os.environ.get("DATABASE_URL")
    if not isinstance(db_url, str) or not db_url:
        raise RuntimeError("DATABASE_URL is not set")

    def _run_in_thread():
        # Create the saver and its DB connection inside the worker thread
        with PostgresSaver.from_conn_string(db_url) as saver:
            saver.setup()
            return run_workflow(
                tpl["path"],
                fn_map=fn_map,
                params=params,
                thread_id=job["id"],
                resume=resume,
                checkpointer=saver,
            )

    result = await asyncio.to_thread(_run_in_thread)
    state = "needs_input" if "__interrupt__" in result else "succeeded"
    return state, result
