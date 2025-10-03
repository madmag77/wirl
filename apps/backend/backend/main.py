from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any, Optional

import dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mcp import FastApiMCP
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

dotenv.load_dotenv()

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


class TemplateInfo(BaseModel):
    id: str
    name: str
    path: str


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
