from __future__ import annotations

import json
import os
import uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

import dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mcp import FastApiMCP
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfoNotFoundError

dotenv.load_dotenv()

from langgraph.checkpoint.postgres import PostgresSaver  # noqa: E402

from backend.database import get_session, init_db  # noqa: E402
from backend.models import (  # noqa: E402
    ContinueWorkflowRequest,
    StartWorkflowRequest,
    TemplateInfo,
    WorkflowDetail,
    WorkflowHistory,
    WorkflowHistoryPage,
    WorkflowResponse,
    WorkflowRun,
    WorkflowRunDetails,
    WorkflowRunStep,
    WorkflowRunWrite,
    WorkflowStatus,
    WorkflowTrigger,
    WorkflowTriggerCreate,
    WorkflowTriggerResponse,
    WorkflowTriggerUpdate,
)
from backend.workflow_loader import get_template, list_templates  # noqa: E402
from backend.scheduler import ScheduleRunner, calculate_next_run


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


schedule_runner = ScheduleRunner()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    schedule_runner.start()
    try:
        yield
    finally:
        await schedule_runner.stop()


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


@app.get("/workflow-triggers", operation_id="getWorkflowTriggers")
def workflow_triggers(db: Session = Depends(get_session)) -> list[WorkflowTriggerResponse]:
    result = db.execute(select(WorkflowTrigger).order_by(WorkflowTrigger.created_at.desc()))
    triggers = result.scalars().all()
    return [WorkflowTriggerResponse.model_validate(trigger) for trigger in triggers]


@app.post("/workflow-triggers", operation_id="createWorkflowTrigger", status_code=201)
def create_workflow_trigger(
    request: WorkflowTriggerCreate,
    db: Session = Depends(get_session),
) -> WorkflowTriggerResponse:
    tpl = get_template(request.template_name)
    if not tpl:
        raise HTTPException(404, "Template not found")

    next_run_at = None
    if request.is_active:
        try:
            next_run_at = calculate_next_run(request.cron, request.timezone)
        except ZoneInfoNotFoundError as exc:
            raise HTTPException(400, f"Unknown timezone '{request.timezone}'") from exc
        except Exception as exc:
            raise HTTPException(400, f"Invalid cron expression: {exc}") from exc

    trigger = WorkflowTrigger(
        name=request.name,
        template_name=tpl["id"],
        cron=request.cron,
        timezone=request.timezone,
        inputs=request.inputs,
        is_active=request.is_active,
        next_run_at=next_run_at,
        last_error=None,
    )
    db.add(trigger)
    db.commit()
    db.refresh(trigger)
    return WorkflowTriggerResponse.model_validate(trigger)


@app.patch("/workflow-triggers/{trigger_id}", operation_id="updateWorkflowTrigger")
def update_workflow_trigger(
    trigger_id: str,
    request: WorkflowTriggerUpdate,
    db: Session = Depends(get_session),
) -> WorkflowTriggerResponse:
    trigger = db.get(WorkflowTrigger, trigger_id)
    if not trigger:
        raise HTTPException(404, "Trigger not found")

    if request.name is not None:
        trigger.name = request.name

    if request.template_name is not None:
        tpl = get_template(request.template_name)
        if not tpl:
            raise HTTPException(404, "Template not found")
        trigger.template_name = tpl["id"]

    if request.cron is not None:
        trigger.cron = request.cron

    if request.timezone is not None:
        trigger.timezone = request.timezone

    if request.inputs is not None:
        trigger.inputs = request.inputs

    if request.is_active is not None:
        trigger.is_active = request.is_active

    if trigger.is_active:
        try:
            trigger.next_run_at = calculate_next_run(
                trigger.cron,
                trigger.timezone,
                from_time=datetime.now(timezone.utc),
            )
            trigger.last_error = None
        except ZoneInfoNotFoundError as exc:
            raise HTTPException(400, f"Unknown timezone '{trigger.timezone}'") from exc
        except Exception as exc:
            raise HTTPException(400, f"Invalid cron expression: {exc}") from exc
    else:
        trigger.next_run_at = None

    db.commit()
    db.refresh(trigger)
    return WorkflowTriggerResponse.model_validate(trigger)


@app.delete("/workflow-triggers/{trigger_id}", operation_id="deleteWorkflowTrigger", status_code=204)
def delete_workflow_trigger(trigger_id: str, db: Session = Depends(get_session)) -> Response:
    trigger = db.get(WorkflowTrigger, trigger_id)
    if not trigger:
        raise HTTPException(404, "Trigger not found")
    db.delete(trigger)
    db.commit()
    return Response(status_code=204)


@app.get("/workflows", operation_id="getWorkflows")
def workflows_history(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
) -> WorkflowHistoryPage:
    total = db.scalar(select(func.count()).select_from(WorkflowRun)) or 0
    result = db.execute(select(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(limit).offset(offset))
    runs = result.scalars().all()
    items = [
        WorkflowHistory(
            id=r.id,
            template=r.graph_name,
            status=WorkflowStatus(r.state),
            created_at=str(r.created_at),
        )
        for r in runs
    ]
    return WorkflowHistoryPage(total=int(total), limit=limit, offset=offset, items=items)


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
