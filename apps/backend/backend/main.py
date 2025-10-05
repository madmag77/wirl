from __future__ import annotations

import json
import os
import uuid
from collections import deque
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any, Iterable, Optional

import dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mcp import FastApiMCP
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

dotenv.load_dotenv()

from langgraph.checkpoint.postgres import PostgresSaver  # noqa: E402

from backend.database import get_session, init_db  # noqa: E402
from backend.models import WorkflowRun  # noqa: E402
from backend.workflow_loader import get_template, list_templates  # noqa: E402


class WorkflowStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    NEEDS_INPUT = "needs_input"
    FAILED = "failed"
    SUCCEEDED = "succeeded"
    CANCELED = "canceled"


# Pydantic models for request/response validation
class StartWorkflowRequest(BaseModel):
    template_name: str
    inputs: dict = {}


class ContinueWorkflowRequest(BaseModel):
    inputs: dict = {}


class WorkflowResponse(BaseModel):
    id: str
    status: WorkflowStatus
    result: dict = {}


class WorkflowDetail(BaseModel):
    id: str
    inputs: dict
    template: str
    status: WorkflowStatus
    result: dict[str, Any]
    error: Optional[str] = None


class WorkflowHistory(BaseModel):
    id: str
    template: str
    status: WorkflowStatus
    created_at: str


class WorkflowRunWrite(BaseModel):
    channel: str
    kind: str
    value: Any


class WorkflowRunStep(BaseModel):
    step: int
    checkpoint_id: str
    timestamp: str
    node: Optional[str]
    task_id: str
    input_state: dict[str, Any]
    output_state: dict[str, Any]
    branches: list[str]
    writes: list[WorkflowRunWrite]


class WorkflowRunDetails(BaseModel):
    run_id: str
    initial_state: dict[str, Any]
    steps: list[WorkflowRunStep]


class TemplateInfo(BaseModel):
    id: str
    name: str
    path: str


def _filter_state(state: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in state.items() if not key.startswith("branch:") and not key.startswith("__")}


def _extract_branch_targets(writes: Optional[Iterable[Any]]) -> deque[str]:
    targets: deque[str] = deque()
    if not writes:
        return targets
    for entry in writes:
        if not entry:
            continue
        if isinstance(entry, dict):
            channel = entry.get("channel")
        elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
            channel = entry[1]
        else:
            channel = None
        if isinstance(channel, str) and channel.startswith("branch:to:"):
            targets.append(channel.split("branch:to:", 1)[1])
    return targets


def _classify_channel(channel: str) -> str:
    if channel.startswith("branch:"):
        return "branch"
    if channel.startswith("__"):
        return "system"
    return "state"


def _group_writes(writes: Optional[Iterable[Any]]) -> list[dict[str, Any]]:
    grouped: list[dict[str, Any]] = []
    if not writes:
        return grouped
    for entry in writes:
        if not entry or len(entry) < 3:
            continue
        task_id, channel, value = entry[:3]
        task_id_str = str(task_id)
        if not grouped or grouped[-1]["task_id"] != task_id_str:
            grouped.append({"task_id": task_id_str, "writes": []})
        grouped[-1]["writes"].append({"channel": channel, "value": value})
    return grouped


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    yield
    # Shutdown
    pass


app = FastAPI(lifespan=lifespan, docs_url="/api/docs")


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all headers
)


@app.get("/workflow-templates", operation_id="getWorkflowTemplates")
def templates() -> list[TemplateInfo]:
    templates_data = list_templates()
    return [TemplateInfo(**template) for template in templates_data]


@app.get("/workflows", operation_id="getWorkflows")
def workflows_history(db: Session = Depends(get_session)) -> list[WorkflowHistory]:
    result = db.execute(select(WorkflowRun))
    runs = result.scalars().all()
    return [
        WorkflowHistory(
            id=r.id,
            template=r.graph_name,
            status=WorkflowStatus(r.state),
            created_at=str(r.created_at),
        )
        for r in runs
    ]


@app.get("/workflows/{workflow_run_id}", operation_id="getWorkflowDetails")
def workflow_detail(workflow_run_id: str, db: Session = Depends(get_session)) -> WorkflowDetail:
    run = db.get(WorkflowRun, workflow_run_id)
    if not run:
        raise HTTPException(404, "Workflow not found")
    return WorkflowDetail(
        id=run.id,
        inputs=run.inputs or {},
        template=run.graph_name,
        status=WorkflowStatus(run.state),
        result=run.result or {},
        error=run.error,
    )


@app.get("/workflows/{workflow_run_id}/run-details", operation_id="getWorkflowRunDetails")
def workflow_run_details(workflow_run_id: str, db: Session = Depends(get_session)) -> WorkflowRunDetails:
    run = db.get(WorkflowRun, workflow_run_id)
    if not run:
        raise HTTPException(404, "Workflow not found")

    thread_id = run.thread_id
    if not thread_id:
        raise HTTPException(400, "Workflow run missing thread identifier")

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(500, "Database configuration missing")

    with PostgresSaver.from_conn_string(db_url) as saver:
        checkpoints = list(saver.list({"configurable": {"thread_id": thread_id}}))

    checkpoints.reverse()  # oldest first

    initial_state: dict[str, Any] = {}
    steps: list[WorkflowRunStep] = []
    current_state: dict[str, Any] = {}
    pending_nodes: deque[str] = deque()

    for checkpoint_tuple in checkpoints:
        checkpoint = checkpoint_tuple.checkpoint or {}
        metadata = checkpoint_tuple.metadata or {}
        pending_writes = checkpoint_tuple.pending_writes or []

        channel_values: dict[str, Any] = dict(checkpoint.get("channel_values") or {})
        filtered_state = _filter_state(channel_values)

        step_number = metadata.get("step")
        if isinstance(step_number, int) and step_number < 0:
            current_state = filtered_state
            initial_state = jsonable_encoder(filtered_state)
            pending_nodes.extend(_extract_branch_targets(pending_writes))
            continue

        grouped_writes = _group_writes(pending_writes)
        if not grouped_writes:
            current_state = filtered_state
            if not initial_state:
                initial_state = jsonable_encoder(filtered_state)
            continue

        for group in grouped_writes:
            node_name = pending_nodes.popleft() if pending_nodes else None
            input_state = jsonable_encoder(current_state)
            state_after = dict(current_state)
            output_changes: dict[str, Any] = {}
            branches: list[str] = []
            formatted_writes: list[WorkflowRunWrite] = []

            for write in group["writes"]:
                channel = str(write.get("channel"))
                value = write.get("value")
                kind = _classify_channel(channel)
                formatted_writes.append(
                    WorkflowRunWrite(
                        channel=channel,
                        kind=kind,
                        value=jsonable_encoder(value),
                    )
                )
                if channel.startswith("branch:to:"):
                    target = channel.split("branch:to:", 1)[1]
                    branches.append(target)
                    pending_nodes.append(target)
                elif kind == "state":
                    state_after[channel] = value
                    output_changes[channel] = value
                    if node_name is None and "." in channel:
                        node_name = channel.split(".", 1)[0]

            current_state = state_after
            steps.append(
                WorkflowRunStep(
                    step=step_number if isinstance(step_number, int) else len(steps),
                    checkpoint_id=str(checkpoint.get("id", "")),
                    timestamp=str(checkpoint.get("ts", "")),
                    node=node_name,
                    task_id=group["task_id"],
                    input_state=input_state,
                    output_state=jsonable_encoder(output_changes),
                    branches=branches,
                    writes=formatted_writes,
                )
            )

        current_state = filtered_state
        if not initial_state:
            initial_state = jsonable_encoder(filtered_state)

    return WorkflowRunDetails(run_id=run.id, initial_state=initial_state, steps=steps)


@app.post("/workflows", operation_id="startWorkflow")
def start_workflow(
    request: StartWorkflowRequest,
    db: Session = Depends(get_session),
) -> WorkflowResponse:
    tpl = get_template(request.template_name)
    if not tpl:
        raise HTTPException(404, "Template not found")
    workflow_run_id = str(uuid.uuid4())
    run = WorkflowRun(
        id=workflow_run_id,
        graph_name=tpl["id"],
        thread_id=workflow_run_id,
        state=WorkflowStatus.QUEUED,
        inputs=request.inputs,
        result={},
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return WorkflowResponse(id=run.id, status=WorkflowStatus(run.state), result={})


@app.post("/workflows/{workflow_run_id}/continue", operation_id="continueWorkflow")
def continue_workflow(
    workflow_run_id: str,
    request: ContinueWorkflowRequest,
    db: Session = Depends(get_session),
) -> WorkflowResponse:
    run = db.get(WorkflowRun, workflow_run_id)
    if not run:
        raise HTTPException(404, "Workflow not found")
    if run.state != WorkflowStatus.NEEDS_INPUT and run.state != WorkflowStatus.FAILED:
        raise HTTPException(400, "Workflow can't be continued")

    if run.state == WorkflowStatus.NEEDS_INPUT:
        run.resume_payload = json.dumps({"answer": request.inputs})

    run.state = WorkflowStatus.QUEUED
    db.commit()
    db.refresh(run)
    return WorkflowResponse(id=run.id, status=run.state, result=run.result or {})


@app.post("/workflows/{workflow_run_id}/cancel", operation_id="cancelWorkflow")
def cancel_workflow(
    workflow_run_id: str,
    db: Session = Depends(get_session),
) -> WorkflowResponse:
    run = db.get(WorkflowRun, workflow_run_id)
    if not run:
        raise HTTPException(404, "Workflow not found")
    if run.state != WorkflowStatus.RUNNING:
        raise HTTPException(400, "Workflow not running")
    run.state = WorkflowStatus.CANCELED
    db.commit()
    db.refresh(run)
    return WorkflowResponse(id=run.id, status=run.state, result=run.result or {})


mcp = FastApiMCP(app, name="workflow runner")
mcp.mount()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
