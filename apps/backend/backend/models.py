from sqlalchemy import Column, String, DateTime, Text, JSON, Integer
from sqlalchemy.sql import func
import uuid

from backend.database import Base

class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    graph_name = Column(String, nullable=False)
    thread_id = Column(String, nullable=False, unique=True)
    state = Column(String, nullable=False, default="queued")
    attempt = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    worker_id = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)
    inputs = Column(JSON, nullable=True)
    resume_payload = Column(Text, nullable=True)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
