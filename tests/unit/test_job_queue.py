"""Tests for P09-03: Queue-backed async job execution.

AC-1: Workers with retry and timeout policies.
AC-2: Job states persisted as queued/running/failed/completed.
AC-3: Dead-letter flow for repeated failures.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from packages.shared.db.models import Base
from packages.shared.job_queue import (
    JobRow,
    JobStatus,
    _JOB_HANDLERS,
    claim_next_job,
    complete_job,
    enqueue_job,
    fail_job,
    get_job,
    list_dead_letter,
    list_jobs,
    process_one_job,
    register_job_handler,
    run_worker_loop,
    _job_info,
)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    # Create all tables including JobRow
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _commit(db: Session):
    db.commit()


# Register test handlers
@register_job_handler("test_success")
def _handle_success(payload: dict) -> dict:
    return {"result": "ok", "input": payload.get("input")}


@register_job_handler("test_fail")
def _handle_fail(payload: dict) -> dict:
    raise ValueError("Simulated failure for testing")


# ---------------------------------------------------------------------------
# AC-2: Job states persisted
# ---------------------------------------------------------------------------

class TestJobStates:
    def test_enqueue_creates_queued_job(self, db: Session):
        job = enqueue_job(db, "test_success", {"input": "data"}, project_id="proj-001")
        _commit(db)
        assert job.status == "queued"
        assert job.attempt == 0

    def test_claim_transitions_to_running(self, db: Session):
        enqueue_job(db, "test_success", {})
        _commit(db)
        job = claim_next_job(db)
        _commit(db)
        assert job is not None
        assert job.status == "running"
        assert job.attempt == 1
        assert job.started_at is not None

    def test_complete_transitions_to_completed(self, db: Session):
        enqueue_job(db, "test_success", {})
        _commit(db)
        job = claim_next_job(db)
        _commit(db)
        completed = complete_job(db, job.id, {"output": "done"})
        _commit(db)
        assert completed.status == "completed"
        assert completed.result_json == {"output": "done"}
        assert completed.completed_at is not None
        assert completed.duration_ms is not None

    def test_fail_requeues_if_attempts_remain(self, db: Session):
        job = enqueue_job(db, "test_fail", {}, max_attempts=3)
        _commit(db)
        claimed = claim_next_job(db)
        _commit(db)
        failed = fail_job(db, claimed.id, "Test error")
        _commit(db)
        assert failed.status == "queued"  # re-queued for retry
        assert failed.attempt == 1
        assert failed.error_message == "Test error"

    def test_get_job(self, db: Session):
        job = enqueue_job(db, "test_success", {"x": 1})
        _commit(db)
        retrieved = get_job(db, job.id)
        assert retrieved is not None
        assert retrieved.payload_json == {"x": 1}

    def test_list_jobs_by_status(self, db: Session):
        enqueue_job(db, "test_success", {})
        j2 = enqueue_job(db, "test_success", {})
        _commit(db)
        claim_next_job(db)
        _commit(db)
        queued = list_jobs(db, status="queued")
        running = list_jobs(db, status="running")
        assert len(queued) == 1
        assert len(running) == 1

    def test_list_jobs_by_project(self, db: Session):
        enqueue_job(db, "test_success", {}, project_id="proj-a")
        enqueue_job(db, "test_success", {}, project_id="proj-b")
        _commit(db)
        assert len(list_jobs(db, project_id="proj-a")) == 1

    def test_job_info_pydantic(self, db: Session):
        job = enqueue_job(db, "test_success", {}, project_id="proj-001")
        _commit(db)
        info = _job_info(job)
        assert info.id == job.id
        assert info.status == "queued"
        assert info.dead_letter is False


# ---------------------------------------------------------------------------
# AC-1: Workers with retry and timeout
# ---------------------------------------------------------------------------

class TestWorkerExecution:
    def test_process_success(self, db: Session):
        enqueue_job(db, "test_success", {"input": "hello"})
        _commit(db)
        processed = process_one_job(db)
        _commit(db)
        assert processed is True
        jobs = list_jobs(db, status="completed")
        assert len(jobs) == 1
        assert jobs[0].result_json["input"] == "hello"

    def test_process_failure_requeues(self, db: Session):
        enqueue_job(db, "test_fail", {}, max_attempts=3)
        _commit(db)
        process_one_job(db)
        _commit(db)
        # Should be re-queued (attempt 1 of 3)
        jobs = list_jobs(db, status="queued")
        assert len(jobs) == 1
        assert jobs[0].attempt == 1

    def test_process_no_handler(self, db: Session):
        enqueue_job(db, "unknown_type", {}, max_attempts=1)
        _commit(db)
        process_one_job(db)
        _commit(db)
        # Should dead-letter immediately (1 attempt, max=1)
        dead = list_dead_letter(db)
        assert len(dead) == 1
        assert "No handler" in dead[0].error_message

    def test_process_empty_queue(self, db: Session):
        assert process_one_job(db) is False

    def test_worker_loop_processes_multiple(self, db: Session):
        engine = db.get_bind()
        Sess = sessionmaker(bind=engine)
        for i in range(3):
            enqueue_job(db, "test_success", {"i": i})
        _commit(db)
        processed = run_worker_loop(Sess, poll_interval=0.01, max_iterations=5)
        assert processed == 3

    def test_retry_then_succeed(self, db: Session):
        """Job fails twice, gets re-queued, then succeeds on third handler."""
        # Use max_attempts=3, fail twice by processing test_fail, then swap
        enqueue_job(db, "test_fail", {}, max_attempts=5)
        _commit(db)

        # Fail attempt 1
        process_one_job(db)
        _commit(db)
        # Fail attempt 2
        process_one_job(db)
        _commit(db)

        # Now change the job type to success (simulating a fix)
        job = list_jobs(db, status="queued")[0]
        job.job_type = "test_success"
        _commit(db)

        process_one_job(db)
        _commit(db)
        completed = list_jobs(db, status="completed")
        assert len(completed) == 1
        assert completed[0].attempt == 3


class TestTimeout:
    def test_timeout_fails_job(self, db: Session):
        """A handler that exceeds timeout should be failed with error_type='timeout'."""
        @register_job_handler("test_slow")
        def _slow(payload):
            import time
            time.sleep(10)
            return {}

        enqueue_job(db, "test_slow", {}, max_attempts=1, timeout_seconds=1)
        _commit(db)
        process_one_job(db)
        _commit(db)
        dead = list_dead_letter(db)
        assert len(dead) == 1
        assert dead[0].error_type == "timeout"
        assert "timed out" in dead[0].error_message

        # Cleanup
        del _JOB_HANDLERS["test_slow"]


# ---------------------------------------------------------------------------
# AC-3: Dead-letter flow
# ---------------------------------------------------------------------------

class TestDeadLetter:
    def test_max_attempts_dead_letters(self, db: Session):
        enqueue_job(db, "test_fail", {}, max_attempts=2)
        _commit(db)

        # Attempt 1: fail -> re-queue
        process_one_job(db)
        _commit(db)
        assert len(list_jobs(db, status="queued")) == 1

        # Attempt 2: fail -> dead letter
        process_one_job(db)
        _commit(db)
        dead = list_dead_letter(db)
        assert len(dead) == 1
        assert dead[0].dead_letter is True
        assert dead[0].status == "dead_letter"
        assert dead[0].attempt == 2

    def test_dead_letter_has_diagnostics(self, db: Session):
        enqueue_job(db, "test_fail", {"context": "important"}, max_attempts=1)
        _commit(db)
        process_one_job(db)
        _commit(db)
        dead = list_dead_letter(db)
        assert len(dead) == 1
        assert dead[0].error_message is not None
        assert "Simulated failure" in dead[0].error_message
        assert dead[0].error_type == "execution_error"
        assert dead[0].payload_json == {"context": "important"}

    def test_dead_letter_not_re_processed(self, db: Session):
        enqueue_job(db, "test_fail", {}, max_attempts=1)
        _commit(db)
        process_one_job(db)
        _commit(db)
        # Dead-lettered job should not be picked up
        assert process_one_job(db) is False

    def test_single_attempt_dead_letters_immediately(self, db: Session):
        enqueue_job(db, "test_fail", {}, max_attempts=1)
        _commit(db)
        process_one_job(db)
        _commit(db)
        assert len(list_dead_letter(db)) == 1
        assert len(list_jobs(db, status="queued")) == 0
