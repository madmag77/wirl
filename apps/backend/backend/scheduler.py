from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import WorkflowRun, WorkflowStatus, WorkflowTrigger
from backend.workflow_loader import get_template

logger = logging.getLogger(__name__)


class CronExpressionError(ValueError):
    """Raised when a cron expression cannot be parsed."""


def calculate_next_run(cron: str, tz_name: str, from_time: Optional[datetime] = None) -> datetime:
    tz = ZoneInfo(tz_name)
    base = (from_time or datetime.now(timezone.utc)).astimezone(tz)
    # croniter treats the base as the "last" execution. Align to the minute to
    # avoid duplicate scheduling when the scheduler polls multiple times within
    # the same minute.
    base = base.replace(second=0, microsecond=0)

    try:
        iterator = croniter(cron, base)
        next_run_local = iterator.get_next(datetime)
    except Exception as exc:  # pragma: no cover - croniter validation
        raise CronExpressionError(str(exc)) from exc

    if next_run_local.tzinfo is None:
        next_run_local = next_run_local.replace(tzinfo=tz)
    return next_run_local.astimezone(timezone.utc)


class ScheduleRunner:
    def __init__(self, poll_interval_seconds: int = 60):
        self._poll_interval_seconds = poll_interval_seconds
        self._task: Optional[asyncio.Task[None]] = None
        self._stopping = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stopping.clear()
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stopping.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def _run(self) -> None:
        while not self._stopping.is_set():
            try:
                self._process_triggers()
            except Exception as exc:  # pragma: no cover - background safety
                logger.exception("Error while processing workflow triggers: %s", exc)
            await asyncio.sleep(self._poll_interval_seconds)

    def _process_triggers(self) -> None:
        with SessionLocal() as session:
            now = datetime.now(timezone.utc)
            # The `FOR UPDATE SKIP LOCKED` clause ensures only one scheduler worker
            # can act on a trigger at a time. Competing transactions skip locked
            # rows instead of blocking, so the first transaction that enqueues a
            # run also refreshes `next_run_at` before the row becomes visible to
            # others, preventing duplicate enqueueing within the same minute.
            triggers = (
                session.execute(
                    select(WorkflowTrigger)
                    .where(
                        WorkflowTrigger.is_active.is_(True),
                        WorkflowTrigger.next_run_at.is_not(None),
                        WorkflowTrigger.next_run_at <= now,
                    )
                    .with_for_update(skip_locked=True)
                )
                .scalars()
                .all()
            )

            for trigger in triggers:
                self._enqueue_trigger_run(session, trigger, now)

            session.commit()

    def _enqueue_trigger_run(self, session: Session, trigger: WorkflowTrigger, now: datetime) -> None:
        template = get_template(trigger.template_name)
        if not template:
            trigger.last_error = f"Template '{trigger.template_name}' not found"
            trigger.is_active = False
            trigger.next_run_at = None
            logger.warning("Disabling trigger %s because template is missing", trigger.id)
            return

        run_id = str(uuid.uuid4())
        run = WorkflowRun(
            id=run_id,
            graph_name=template["id"],
            thread_id=run_id,
            state=WorkflowStatus.QUEUED,
            inputs=trigger.inputs or {},
            result={},
        )
        session.add(run)
        trigger.last_run_at = now
        trigger.last_error = None
        try:
            # Always calculate next run from NOW to skip all missed runs.
            # This ensures that if the system was down for multiple scheduled runs,
            # we only enqueue ONE job (the most recent missed one) and then schedule
            # the next run in the future, rather than enqueueing all missed runs.
            trigger.next_run_at = calculate_next_run(
                trigger.cron,
                trigger.timezone,
                from_time=now,
            )
        except Exception as exc:
            trigger.next_run_at = None
            trigger.is_active = False
            trigger.last_error = str(exc)
            logger.warning("Failed to calculate next run for trigger %s: %s", trigger.id, exc)


def initialize_trigger_schedule(session: Session, trigger: WorkflowTrigger) -> None:
    if not trigger.is_active:
        trigger.next_run_at = None
        return

    try:
        trigger.next_run_at = calculate_next_run(trigger.cron, trigger.timezone)
        trigger.last_error = None
    except Exception as exc:
        trigger.next_run_at = None
        trigger.last_error = str(exc)
        trigger.is_active = False
        logger.warning("Trigger %s disabled due to invalid schedule: %s", trigger.id, exc)

    session.add(trigger)
