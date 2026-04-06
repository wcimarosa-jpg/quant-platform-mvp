"""Queue-backed asynchronous job execution.

Runs heavy analyses (table generation, drivers, segmentation, MaxDiff)
through a persistent job queue with retry, timeout, and dead-letter
handling. Jobs are stored in the DB and executed by worker threads.

AC-1: Workers with retry + timeout
AC-2: Persisted job states (queued/running/failed/completed)
AC-3: Dead-letter flow for repeated failures
"""

from __future__ import annotations

import logging
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, JSON, Index
from sqlalchemy.orm import Session

from .db.models import Base

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DB Model
# ---------------------------------------------------------------------------

class JobRow(Base):
    __tablename__ = "job_queue"

    id = Column(String(64), primary_key=True)
    job_type = Column(String(100), nullable=False)
    project_id = Column(String(64), index=True)
    status = Column(String(20), nullable=False, default="queued")
    payload_json = Column(JSON)
    result_json = Column(JSON)
    error_message = Column(Text)
    error_type = Column(String(50))
    attempt = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    timeout_seconds = Column(Integer, nullable=False, default=300)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=timezone.utc))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)
    dead_letter = Column(Boolean, default=False)

    __table_args__ = (
        Index("ix_job_status", "status"),
    )


# ---------------------------------------------------------------------------
# Job states
# ---------------------------------------------------------------------------

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


# ---------------------------------------------------------------------------
# Pydantic models for API
# ---------------------------------------------------------------------------

class JobInfo(BaseModel):
    id: str
    job_type: str
    project_id: str | None
    status: str
    attempt: int
    max_attempts: int
    error_message: str | None = None
    error_type: str | None = None
    dead_letter: bool = False
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None


def _job_info(row: JobRow) -> JobInfo:
    return JobInfo(
        id=row.id, job_type=row.job_type, project_id=row.project_id,
        status=row.status, attempt=row.attempt, max_attempts=row.max_attempts,
        error_message=row.error_message, error_type=row.error_type,
        dead_letter=bool(row.dead_letter),
        created_at=row.created_at, started_at=row.started_at,
        completed_at=row.completed_at, duration_ms=row.duration_ms,
    )


# ---------------------------------------------------------------------------
# Queue operations
# ---------------------------------------------------------------------------

def enqueue_job(
    db: Session,
    job_type: str,
    payload: dict[str, Any],
    project_id: str | None = None,
    max_attempts: int = 3,
    timeout_seconds: int = 300,
) -> JobRow:
    """Create a new job in QUEUED status."""
    job = JobRow(
        id=f"job-{uuid.uuid4().hex[:12]}",
        job_type=job_type,
        project_id=project_id,
        status=JobStatus.QUEUED.value,
        payload_json=payload,
        max_attempts=max_attempts,
        timeout_seconds=timeout_seconds,
    )
    db.add(job)
    db.flush()
    return job


def claim_next_job(db: Session, job_type: str | None = None) -> JobRow | None:
    """Atomically claim the oldest QUEUED job. Sets status to RUNNING.

    Uses with_for_update() on PostgreSQL for row-level locking.
    On SQLite, serialized writes prevent races.
    """
    q = db.query(JobRow).filter(JobRow.status == JobStatus.QUEUED.value)
    if job_type:
        q = q.filter(JobRow.job_type == job_type)
    q = q.order_by(JobRow.created_at.asc())

    # Use FOR UPDATE if available (PostgreSQL), no-op on SQLite
    try:
        job = q.with_for_update(skip_locked=True).first()
    except Exception:
        # SQLite doesn't support FOR UPDATE — fall back to plain query
        job = q.first()

    if not job:
        return None
    job.status = JobStatus.RUNNING.value
    job.started_at = _utcnow_naive()
    job.attempt += 1
    db.flush()
    return job


def _utcnow_naive() -> datetime:
    """Naive UTC datetime — avoids timezone mixing with SQLite."""
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


def complete_job(db: Session, job_id: str, result: dict[str, Any] | None = None) -> JobRow | None:
    """Mark job as COMPLETED."""
    job = db.query(JobRow).filter(JobRow.id == job_id).first()
    if not job:
        return None
    job.status = JobStatus.COMPLETED.value
    job.result_json = result
    now = _utcnow_naive()
    job.completed_at = now
    if job.started_at:
        started = job.started_at.replace(tzinfo=None) if job.started_at.tzinfo else job.started_at
        job.duration_ms = int((now - started).total_seconds() * 1000)
    db.flush()
    return job


def fail_job(
    db: Session,
    job_id: str,
    error_message: str,
    error_type: str = "execution_error",
) -> JobRow | None:
    """Mark job as FAILED. If max_attempts exceeded, move to dead letter."""
    job = db.query(JobRow).filter(JobRow.id == job_id).first()
    if not job:
        return None
    job.error_message = error_message
    job.error_type = error_type
    now = _utcnow_naive()
    job.completed_at = now
    if job.started_at:
        started = job.started_at.replace(tzinfo=None) if job.started_at.tzinfo else job.started_at
        job.duration_ms = int((now - started).total_seconds() * 1000)

    if job.attempt >= job.max_attempts:
        job.status = JobStatus.DEAD_LETTER.value
        job.dead_letter = True
        logger.warning(f"Job {job_id} moved to dead letter after {job.attempt} attempts: {error_message}")
    else:
        job.status = JobStatus.QUEUED.value  # re-queue for retry
        logger.info(f"Job {job_id} failed (attempt {job.attempt}/{job.max_attempts}), re-queued: {error_message}")
    db.flush()
    return job


def get_job(db: Session, job_id: str) -> JobRow | None:
    return db.query(JobRow).filter(JobRow.id == job_id).first()


def list_jobs(
    db: Session,
    status: str | None = None,
    project_id: str | None = None,
    limit: int = 50,
) -> list[JobRow]:
    q = db.query(JobRow)
    if status:
        q = q.filter(JobRow.status == status)
    if project_id:
        q = q.filter(JobRow.project_id == project_id)
    return q.order_by(JobRow.created_at.desc()).limit(limit).all()


def list_dead_letter(db: Session, limit: int = 50) -> list[JobRow]:
    """Return dead-lettered jobs with actionable diagnostics."""
    return (
        db.query(JobRow)
        .filter(JobRow.dead_letter == True)
        .order_by(JobRow.completed_at.desc())
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# Worker (in-process thread pool)
# ---------------------------------------------------------------------------

# Registry: job_type -> handler function
_JOB_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}


def register_job_handler(job_type: str) -> Callable:
    """Decorator to register a job handler."""
    def decorator(fn: Callable[[dict[str, Any]], dict[str, Any]]) -> Callable:
        _JOB_HANDLERS[job_type] = fn
        return fn
    return decorator


def process_one_job(db: Session) -> bool:
    """Claim and process one job with timeout enforcement.

    Uses concurrent.futures.ThreadPoolExecutor to enforce timeout_seconds.
    Returns True if a job was processed.
    """
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

    job = claim_next_job(db)
    if not job:
        return False

    handler = _JOB_HANDLERS.get(job.job_type)
    if not handler:
        fail_job(db, job.id, f"No handler for job_type={job.job_type!r}", "unknown_job_type")
        return True

    timeout = job.timeout_seconds or 300

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(handler, job.payload_json or {})
            result = future.result(timeout=timeout)
        complete_job(db, job.id, result)
    except FuturesTimeout:
        fail_job(db, job.id, f"Job timed out after {timeout}s", "timeout")
    except Exception as exc:
        fail_job(db, job.id, f"{type(exc).__name__}: {exc}", "execution_error")

    return True


def run_worker_loop(
    session_factory: Callable[[], Session],
    poll_interval: float = 2.0,
    max_iterations: int | None = None,
) -> int:
    """Poll for jobs and process them. Returns total jobs processed.

    Args:
        session_factory: Callable that returns a new DB session.
        poll_interval: Seconds between polls when idle.
        max_iterations: Stop after N iterations (None = run forever).
    """
    processed = 0
    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        iterations += 1
        db = session_factory()
        try:
            if process_one_job(db):
                db.commit()
                processed += 1
            else:
                time.sleep(poll_interval)
        except Exception as exc:
            logger.error(f"Worker error: {exc}")
            db.rollback()
        finally:
            db.close()
    return processed
