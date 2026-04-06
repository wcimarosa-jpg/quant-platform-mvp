"""Idempotency keys and duplicate-run protection.

Provides idempotency enforcement for analysis runs and general-purpose
create-or-return semantics for any entity with an idempotency_key column.

Integrates with:
- db/models.py (AnalysisRunRow.idempotency_key)
- job_queue.py (JobRow.idempotency_key, DuplicateJobError)
- db/repository.py (save_run, get_run)
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db.models import AnalysisRunRow

logger = logging.getLogger(__name__)


class DuplicateRunError(Exception):
    """Raised when an analysis run with the same idempotency key exists."""

    def __init__(self, run_id: str, status: str) -> None:
        self.run_id = run_id
        self.status = status
        super().__init__(
            f"Analysis run already exists with this idempotency key "
            f"(run_id={run_id!r}, status={status!r})."
        )


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------

def _stable_value(v: Any) -> str:
    """Produce a stable string representation of a param value."""
    return json.dumps(v, sort_keys=True, default=str)


def generate_idempotency_key(
    project_id: str,
    operation: str,
    *,
    params: dict[str, Any] | None = None,
    nonce: str | None = None,
) -> str:
    """Generate a deterministic idempotency key from operation parameters.

    The key is a SHA-256 hash of the project, operation, and JSON-serialized
    params. If nonce is provided, it is included to allow intentional re-runs.

    Args:
        project_id: The project context.
        operation: Operation name (e.g. 'drivers', 'segmentation', 'table_gen').
        params: Serializable parameters that distinguish this run.
        nonce: Optional unique value to force a new key.

    Returns:
        A hex string suitable for use as an idempotency key.
    """
    parts = [project_id, operation]
    if params:
        for k in sorted(params.keys()):
            parts.append(f"{k}={_stable_value(params[k])}")
    if nonce:
        parts.append(f"nonce={nonce}")
    raw = "\x00".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()


def make_random_idempotency_key() -> str:
    """Generate a random idempotency key (for one-shot operations)."""
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# Analysis run deduplication
# ---------------------------------------------------------------------------

def get_run_by_idempotency_key(db: Session, idempotency_key: str) -> AnalysisRunRow | None:
    """Look up an analysis run by idempotency key."""
    return (
        db.query(AnalysisRunRow)
        .filter(AnalysisRunRow.idempotency_key == idempotency_key)
        .first()
    )


def create_run_idempotent(
    db: Session,
    run_id: str,
    project_id: str,
    analysis_type: str,
    idempotency_key: str,
    config: dict[str, Any] | None = None,
    status: str = "queued",
) -> tuple[AnalysisRunRow, bool]:
    """Create an analysis run with idempotency protection.

    Returns (run, created) where created=True if a new run was made,
    or created=False if an existing run with the same key was found.

    Raises DuplicateRunError only if the existing run belongs to a
    different project (cross-project collision).

    Handles the TOCTOU race: if two concurrent requests pass the initial
    check, the unique constraint catches the second insert and we re-query.
    """
    existing = get_run_by_idempotency_key(db, idempotency_key)
    if existing:
        if existing.project_id != project_id:
            logger.warning(
                "Idempotency key collision across projects: key=%s, "
                "existing_project=%s, requested_project=%s",
                idempotency_key, existing.project_id, project_id,
            )
            raise DuplicateRunError(existing.id, existing.status)
        return existing, False

    run = AnalysisRunRow(
        id=run_id,
        project_id=project_id,
        analysis_type=analysis_type,
        status=status,
        idempotency_key=idempotency_key,
        config_json=config,
    )
    db.add(run)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = get_run_by_idempotency_key(db, idempotency_key)
        if existing:
            if existing.project_id != project_id:
                raise DuplicateRunError(existing.id, existing.status)
            return existing, False
        raise  # re-raise if it was a different constraint
    return run, True


# ---------------------------------------------------------------------------
# Duplicate-run detection for active runs
# ---------------------------------------------------------------------------

_ACTIVE_STATUSES = {"queued", "running"}


def check_duplicate_active_run(
    db: Session,
    project_id: str,
    analysis_type: str,
) -> AnalysisRunRow | None:
    """Check if there is already a queued or running analysis of the same type.

    Returns the existing active run if found, None otherwise.

    Note: This is an advisory check — it does not acquire locks. Callers
    should rely on the idempotency_key unique constraint as the true
    guard against duplicate runs. This function is useful for giving
    early user-facing feedback before attempting to create a run.
    """
    return (
        db.query(AnalysisRunRow)
        .filter(
            AnalysisRunRow.project_id == project_id,
            AnalysisRunRow.analysis_type == analysis_type,
            AnalysisRunRow.status.in_(_ACTIVE_STATUSES),
        )
        .order_by(AnalysisRunRow.created_at.desc())
        .first()
    )
