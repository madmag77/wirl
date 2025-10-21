from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    graph_name: Mapped[str] = mapped_column(String, nullable=False)
    thread_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    state: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    worker_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    inputs: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    resume_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())


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
    inputs: dict[str, Any] = Field(default_factory=dict)


class ContinueWorkflowRequest(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: WorkflowStatus
    result: dict[str, Any] = Field(default_factory=dict)


class WorkflowDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    inputs: dict
    template: str
    status: WorkflowStatus
    result: dict[str, Any]
    error: Optional[str] = None


class WorkflowHistory(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    template: str
    status: WorkflowStatus
    created_at: str


class WorkflowHistoryPage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total: int
    limit: int
    offset: int
    items: list[WorkflowHistory]


class WorkflowRunWrite(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    channel: str
    kind: str
    value: Any


class WorkflowRunStep(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    initial_state: dict[str, Any]
    steps: list[WorkflowRunStep]


class TemplateInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    path: str


class WorkflowTrigger(Base):
    """Represents a persisted schedule that can enqueue workflow runs automatically."""

    __tablename__ = "workflow_triggers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    template_name: Mapped[str] = mapped_column(String, nullable=False)
    cron: Mapped[str] = mapped_column(String, nullable=False)
    timezone: Mapped[str] = mapped_column(String, nullable=False, default="UTC")
    inputs: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="JSON payload that becomes the default workflow inputs for the trigger",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="If false the trigger is ignored by the scheduler",
    )
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class WorkflowTriggerBase(BaseModel):
    name: str
    template_name: str
    cron: str
    timezone: str = Field(default="UTC", description="IANA timezone used to evaluate the cron expression")
    inputs: dict[str, Any] = Field(
        default_factory=dict,
        description="Default workflow inputs applied to each scheduled run",
    )
    is_active: bool = Field(default=True, description="Pause scheduling without removing the trigger")


class WorkflowTriggerCreate(WorkflowTriggerBase):
    pass


class WorkflowTriggerUpdate(BaseModel):
    name: Optional[str] = None
    template_name: Optional[str] = None
    cron: Optional[str] = None
    timezone: Optional[str] = None
    inputs: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class WorkflowTriggerResponse(WorkflowTriggerBase):
    id: str
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
