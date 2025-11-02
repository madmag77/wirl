"""Tests for the scheduler module."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.database import Base
from backend.models import WorkflowRun, WorkflowStatus, WorkflowTrigger
from backend.scheduler import ScheduleRunner, calculate_next_run


@pytest.fixture
def test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)
    session = TestSessionLocal()

    # Create a mock context manager that yields our test session
    class MockSessionLocal:
        def __call__(self):
            return self

        def __enter__(self):
            return session

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                session.commit()
            else:
                session.rollback()
            # Don't close the session so it persists for test assertions
            return False

    # Patch SessionLocal to use our mock
    with patch("backend.scheduler.SessionLocal", MockSessionLocal()):
        yield session

    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def mock_template():
    """Mock the get_template function to return a valid template."""
    with patch("backend.scheduler.get_template") as mock:
        mock.return_value = {
            "id": "test_workflow",
            "name": "Test Workflow",
        }
        yield mock


class TestCalculateNextRun:
    """Tests for the calculate_next_run function."""

    def test_calculates_next_run_from_now(self):
        """Test calculating next run from current time."""
        # Every day at 9 AM
        cron = "0 9 * * *"
        next_run = calculate_next_run(cron, "UTC")

        now = datetime.now(timezone.utc)
        assert next_run > now
        assert next_run.hour == 9
        assert next_run.minute == 0
        assert next_run.second == 0

    def test_calculates_next_run_from_specific_time(self):
        """Test calculating next run from a specific time."""
        # Every hour at minute 30
        cron = "30 * * * *"
        base_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

        next_run = calculate_next_run(cron, "UTC", from_time=base_time)

        assert next_run == datetime(2024, 1, 1, 10, 30, 0, tzinfo=timezone.utc)

    def test_respects_timezone(self):
        """Test that timezone is properly respected."""
        # Every day at 9 AM
        cron = "0 9 * * *"
        base_time = datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)

        # Calculate for New York (EST/EDT)
        next_run = calculate_next_run(cron, "America/New_York", from_time=base_time)

        # 9 AM in New York is typically 14:00 UTC (EST) or 13:00 UTC (EDT)
        assert next_run.hour in [13, 14]  # Account for DST
        assert next_run.minute == 0

    def test_handles_invalid_cron(self):
        """Test that invalid cron expressions raise an error."""
        with pytest.raises(Exception):
            calculate_next_run("invalid cron", "UTC")


class TestScheduleRunnerSingleMissedRun:
    """Tests for handling a single missed run."""

    def test_enqueues_single_missed_run(self, test_db: Session, mock_template):
        """Test that a single missed run is enqueued correctly."""
        scheduler = ScheduleRunner()

        # Create a trigger that should have run 30 minutes ago
        now = datetime.now(timezone.utc)
        missed_run_time = now - timedelta(minutes=30)

        trigger = WorkflowTrigger(
            id="test-trigger-1",
            name="Test Trigger",
            template_name="test_workflow",
            cron="0 * * * *",  # Every hour
            timezone="UTC",
            inputs={"key": "value"},
            is_active=True,
            next_run_at=missed_run_time,
        )
        test_db.add(trigger)
        test_db.commit()

        # Process triggers
        scheduler._process_triggers()

        # Verify a workflow run was created
        runs = test_db.query(WorkflowRun).all()
        assert len(runs) == 1
        assert runs[0].graph_name == "test_workflow"
        assert runs[0].state == WorkflowStatus.QUEUED
        assert runs[0].inputs == {"key": "value"}

        # Verify trigger was updated
        test_db.refresh(trigger)
        assert trigger.last_run_at is not None
        # SQLite may return timezone-naive datetimes, normalize for comparison
        last_run_tz_aware = trigger.last_run_at.replace(tzinfo=timezone.utc) if trigger.last_run_at.tzinfo is None else trigger.last_run_at
        next_run_tz_aware = trigger.next_run_at.replace(tzinfo=timezone.utc) if trigger.next_run_at.tzinfo is None else trigger.next_run_at
        assert last_run_tz_aware > missed_run_time
        assert next_run_tz_aware > now  # Next run should be in the future
        assert trigger.last_error is None

    def test_single_missed_run_calculates_from_missed_time(self, test_db: Session, mock_template):
        """Test that for a single miss, next run is calculated from the missed time."""
        scheduler = ScheduleRunner()

        # Create a trigger that missed one run 5 minutes ago
        # Cron: every hour on the hour
        # This ensures the next run after the missed one is still in the future
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        missed_run_time = now - timedelta(minutes=5)

        trigger = WorkflowTrigger(
            id="test-trigger-2",
            name="Test Trigger",
            template_name="test_workflow",
            cron="0 * * * *",  # Every hour on the hour
            timezone="UTC",
            inputs={},
            is_active=True,
            next_run_at=missed_run_time,
        )
        test_db.add(trigger)
        test_db.commit()

        # Process triggers
        scheduler._process_triggers()

        # Verify trigger next_run_at is calculated from the missed time
        test_db.refresh(trigger)

        # The next run should be approximately 55 minutes from now
        # (60 minutes after the missed time)
        assert trigger.next_run_at is not None

        # Ensure both datetimes are timezone-aware for comparison
        if trigger.next_run_at.tzinfo is None:
            trigger_next_run = trigger.next_run_at.replace(tzinfo=timezone.utc)
        else:
            trigger_next_run = trigger.next_run_at

        # The next run should be in the future (more than current time)
        assert trigger_next_run > now
        # Should be less than 2 hours from now (since cron is hourly)
        assert trigger_next_run < now + timedelta(hours=2)


class TestScheduleRunnerMultipleMissedRuns:
    """Tests for handling multiple missed runs (the new fix)."""

    def test_skips_multiple_missed_runs(self, test_db: Session, mock_template):
        """Test that multiple missed runs result in only one execution and skip ahead."""
        scheduler = ScheduleRunner()

        # Create a trigger that missed multiple runs
        # Cron: every hour, last run was 7 days ago
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        missed_run_time = now - timedelta(days=7)

        trigger = WorkflowTrigger(
            id="test-trigger-3",
            name="Test Daily Trigger",
            template_name="test_workflow",
            cron="0 9 * * *",  # Every day at 9 AM
            timezone="UTC",
            inputs={"analysis": "yesterday_to_today"},
            is_active=True,
            next_run_at=missed_run_time,
        )
        test_db.add(trigger)
        test_db.commit()

        # Process triggers
        scheduler._process_triggers()

        # Verify only ONE workflow run was created
        runs = test_db.query(WorkflowRun).all()
        assert len(runs) == 1, "Should only create one run despite missing 7 days"

        # Verify trigger next_run_at skipped ahead to future
        test_db.refresh(trigger)
        # SQLite may return timezone-naive datetimes
        next_run_tz_aware = trigger.next_run_at.replace(tzinfo=timezone.utc) if trigger.next_run_at.tzinfo is None else trigger.next_run_at
        assert next_run_tz_aware > now, "Next run should be in the future"

        # The next run should be tomorrow at 9 AM (approximately)
        expected_next = now + timedelta(days=1)
        time_difference = abs((next_run_tz_aware - expected_next).total_seconds())
        assert time_difference < 3600 * 24  # Within a day

    def test_multiple_missed_runs_logs_message(self, test_db: Session, mock_template, caplog):
        """Test that skipping multiple runs logs an informative message."""
        scheduler = ScheduleRunner()

        # Create a trigger that missed multiple runs
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        missed_run_time = now - timedelta(days=3)

        trigger = WorkflowTrigger(
            id="test-trigger-4",
            name="Test Trigger",
            template_name="test_workflow",
            cron="0 12 * * *",  # Every day at noon
            timezone="UTC",
            inputs={},
            is_active=True,
            next_run_at=missed_run_time,
        )
        test_db.add(trigger)
        test_db.commit()

        # Process triggers with logging
        with caplog.at_level("INFO"):
            scheduler._process_triggers()

        # Check that the log message was generated
        assert any("missed multiple scheduled runs" in record.message.lower() for record in caplog.records), "Should log a message about missing multiple runs"

    def test_prevents_cascade_of_old_jobs(self, test_db: Session, mock_template):
        """Test that old jobs don't cascade by processing each day sequentially."""
        scheduler = ScheduleRunner()

        # Create a trigger that was supposed to run daily for the past week
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        week_ago = now - timedelta(days=7)

        trigger = WorkflowTrigger(
            id="test-trigger-5",
            name="Daily Analysis",
            template_name="test_workflow",
            cron="0 6 * * *",  # Every day at 6 AM
            timezone="UTC",
            inputs={},
            is_active=True,
            next_run_at=week_ago,
        )
        test_db.add(trigger)
        test_db.commit()

        # Process triggers ONCE
        scheduler._process_triggers()

        # Should only create 1 run
        runs = test_db.query(WorkflowRun).all()
        assert len(runs) == 1, "Should not cascade through all 7 missed days"

        # Process again immediately (simulating the next poll cycle)
        scheduler._process_triggers()

        # Should still be only 1 run (no new run created)
        runs = test_db.query(WorkflowRun).all()
        assert len(runs) == 1, "Should not create additional runs"

        # Verify next run is in the future
        test_db.refresh(trigger)
        # SQLite may return timezone-naive datetimes
        next_run_tz_aware = trigger.next_run_at.replace(tzinfo=timezone.utc) if trigger.next_run_at.tzinfo is None else trigger.next_run_at
        assert next_run_tz_aware > now


class TestScheduleRunnerEdgeCases:
    """Tests for edge cases and error handling."""

    def test_inactive_trigger_not_processed(self, test_db: Session, mock_template):
        """Test that inactive triggers are not processed."""
        scheduler = ScheduleRunner()

        now = datetime.now(timezone.utc)
        trigger = WorkflowTrigger(
            id="test-trigger-6",
            name="Inactive Trigger",
            template_name="test_workflow",
            cron="* * * * *",
            timezone="UTC",
            inputs={},
            is_active=False,  # Inactive
            next_run_at=now - timedelta(minutes=5),
        )
        test_db.add(trigger)
        test_db.commit()

        scheduler._process_triggers()

        # No runs should be created
        runs = test_db.query(WorkflowRun).all()
        assert len(runs) == 0

    def test_missing_template_disables_trigger(self, test_db: Session):
        """Test that a trigger with a missing template gets disabled."""
        with patch("backend.scheduler.get_template") as mock:
            mock.return_value = None  # Template not found

            scheduler = ScheduleRunner()

            now = datetime.now(timezone.utc)
            trigger = WorkflowTrigger(
                id="test-trigger-7",
                name="Missing Template Trigger",
                template_name="nonexistent_workflow",
                cron="* * * * *",
                timezone="UTC",
                inputs={},
                is_active=True,
                next_run_at=now - timedelta(minutes=5),
            )
            test_db.add(trigger)
            test_db.commit()

            scheduler._process_triggers()

            # No runs should be created
            runs = test_db.query(WorkflowRun).all()
            assert len(runs) == 0

            # Trigger should be disabled
            test_db.refresh(trigger)
            assert trigger.is_active is False
            assert trigger.last_error is not None
            assert "not found" in trigger.last_error.lower()

    def test_future_next_run_not_processed(self, test_db: Session, mock_template):
        """Test that triggers scheduled for the future are not processed."""
        scheduler = ScheduleRunner()

        now = datetime.now(timezone.utc)
        trigger = WorkflowTrigger(
            id="test-trigger-8",
            name="Future Trigger",
            template_name="test_workflow",
            cron="0 9 * * *",
            timezone="UTC",
            inputs={},
            is_active=True,
            next_run_at=now + timedelta(hours=2),  # Future
        )
        test_db.add(trigger)
        test_db.commit()

        scheduler._process_triggers()

        # No runs should be created
        runs = test_db.query(WorkflowRun).all()
        assert len(runs) == 0

    def test_null_next_run_at_not_processed(self, test_db: Session, mock_template):
        """Test that triggers with null next_run_at are not processed."""
        scheduler = ScheduleRunner()

        trigger = WorkflowTrigger(
            id="test-trigger-9",
            name="Null Next Run Trigger",
            template_name="test_workflow",
            cron="0 9 * * *",
            timezone="UTC",
            inputs={},
            is_active=True,
            next_run_at=None,  # No scheduled run
        )
        test_db.add(trigger)
        test_db.commit()

        scheduler._process_triggers()

        # No runs should be created
        runs = test_db.query(WorkflowRun).all()
        assert len(runs) == 0

    def test_cron_calculation_error_disables_trigger(self, test_db: Session, mock_template):
        """Test that errors during cron calculation disable the trigger."""
        scheduler = ScheduleRunner()

        now = datetime.now(timezone.utc)
        trigger = WorkflowTrigger(
            id="test-trigger-10",
            name="Bad Cron Trigger",
            template_name="test_workflow",
            cron="0 9 * * *",  # Valid initially
            timezone="UTC",
            inputs={},
            is_active=True,
            next_run_at=now - timedelta(minutes=5),
        )
        test_db.add(trigger)
        test_db.commit()

        # Mock calculate_next_run to raise an error
        with patch("backend.scheduler.calculate_next_run") as mock_calc:
            mock_calc.side_effect = Exception("Invalid cron expression")

            scheduler._process_triggers()

            # A run should still be created (before the error)
            # Actually, the first call succeeds (checking for multiple missed)
            # The second call in the try block fails
            test_db.refresh(trigger)
            assert trigger.is_active is False
            assert trigger.last_error is not None
            assert "invalid cron expression" in trigger.last_error.lower()


class TestScheduleRunnerMultipleTriggers:
    """Tests for processing multiple triggers."""

    def test_processes_multiple_triggers(self, test_db: Session, mock_template):
        """Test that multiple triggers are processed correctly."""
        scheduler = ScheduleRunner()

        now = datetime.now(timezone.utc)

        # Create two triggers
        trigger1 = WorkflowTrigger(
            id="test-trigger-11",
            name="Trigger 1",
            template_name="test_workflow",
            cron="* * * * *",
            timezone="UTC",
            inputs={"id": 1},
            is_active=True,
            next_run_at=now - timedelta(minutes=5),
        )
        trigger2 = WorkflowTrigger(
            id="test-trigger-12",
            name="Trigger 2",
            template_name="test_workflow",
            cron="* * * * *",
            timezone="UTC",
            inputs={"id": 2},
            is_active=True,
            next_run_at=now - timedelta(minutes=3),
        )
        test_db.add(trigger1)
        test_db.add(trigger2)
        test_db.commit()

        scheduler._process_triggers()

        # Both should create runs
        runs = test_db.query(WorkflowRun).all()
        assert len(runs) == 2

        # Verify correct inputs
        inputs_list = [run.inputs for run in runs]
        assert {"id": 1} in inputs_list
        assert {"id": 2} in inputs_list
