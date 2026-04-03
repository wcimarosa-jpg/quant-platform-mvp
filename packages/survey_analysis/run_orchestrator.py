"""Analysis run orchestrator.

Launches analysis runs with status tracking, version provenance,
and actionable failure messages. Runs are executed synchronously
in this implementation; async worker integration is deferred.
"""

from __future__ import annotations

import json
import traceback
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    FAILED = "failed"
    COMPLETED = "completed"


class RunConfig(BaseModel):
    """Configuration for an analysis run."""

    analysis_type: str                  # e.g., "kmeans", "drivers", "maxdiff", "crosstabs"
    parameters: dict[str, Any] = Field(default_factory=dict)


class RunVersions(BaseModel):
    """Input version provenance for an analysis run."""

    questionnaire_id: str
    questionnaire_version: int
    mapping_id: str
    mapping_version: int
    data_file_hash: str


class AnalysisRun(BaseModel):
    """One tracked analysis run with full lifecycle metadata."""

    run_id: str = Field(default_factory=lambda: f"run-{uuid.uuid4().hex[:8]}")
    project_id: str
    status: RunStatus = RunStatus.QUEUED
    config: RunConfig
    versions: RunVersions
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    error_message: str | None = None
    error_type: str | None = None
    result_summary: dict[str, Any] | None = None

    def is_terminal(self) -> bool:
        return self.status in (RunStatus.COMPLETED, RunStatus.FAILED)

    def provenance(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "project_id": self.project_id,
            "analysis_type": self.config.analysis_type,
            "status": self.status.value,
            "versions": self.versions.model_dump(),
            "parameters": self.config.parameters,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
        }


class AnalysisError(Exception):
    """Raised by analysis functions with an actionable message."""

    def __init__(self, message: str, error_type: str = "analysis_error") -> None:
        self.error_type = error_type
        super().__init__(message)


# ---------------------------------------------------------------------------
# Run store
# ---------------------------------------------------------------------------

class RunStore:
    """In-memory run store with project-level queries.

    TODO: Back with database for persistence.
    """

    def __init__(self) -> None:
        self._runs: dict[str, AnalysisRun] = {}

    def save(self, run: AnalysisRun) -> None:
        self._runs[run.run_id] = run

    def get(self, run_id: str) -> AnalysisRun | None:
        return self._runs.get(run_id)

    def get_by_project(self, project_id: str) -> list[AnalysisRun]:
        return [r for r in self._runs.values() if r.project_id == project_id]

    def get_by_status(self, status: RunStatus) -> list[AnalysisRun]:
        return [r for r in self._runs.values() if r.status == status]

    @property
    def count(self) -> int:
        return len(self._runs)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

# Registry of analysis functions keyed by analysis_type.
# Each function receives (run: AnalysisRun, **kwargs) and returns a result summary dict.
# Raise AnalysisError for actionable failures.
_ANALYSIS_REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {}


def register_analysis(analysis_type: str) -> Callable:
    """Decorator to register an analysis function."""
    def decorator(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
        _ANALYSIS_REGISTRY[analysis_type] = fn
        return fn
    return decorator


def get_registered_types() -> list[str]:
    """Return list of registered analysis types."""
    return sorted(_ANALYSIS_REGISTRY.keys())


def create_run(
    project_id: str,
    config: RunConfig,
    versions: RunVersions,
    store: RunStore | None = None,
) -> AnalysisRun:
    """Create a new run in QUEUED status and persist it."""
    run = AnalysisRun(
        project_id=project_id,
        config=config,
        versions=versions,
    )
    if store:
        store.save(run)
    return run


def execute_run(
    run: AnalysisRun,
    store: RunStore | None = None,
    **kwargs: Any,
) -> AnalysisRun:
    """Execute an analysis run synchronously.

    Transitions: QUEUED → RUNNING → COMPLETED or FAILED.
    On failure, ``run.error_message`` contains an actionable description.
    """
    if run.status != RunStatus.QUEUED:
        raise ValueError(f"Cannot execute run in status {run.status.value!r}. Must be QUEUED.")

    analysis_fn = _ANALYSIS_REGISTRY.get(run.config.analysis_type)
    if not analysis_fn:
        run.status = RunStatus.FAILED
        run.error_message = (
            f"Unknown analysis type: {run.config.analysis_type!r}. "
            f"Registered types: {', '.join(get_registered_types()) or 'none'}."
        )
        run.error_type = "unknown_analysis_type"
        if store:
            store.save(run)
        return run

    # Transition to RUNNING
    run.status = RunStatus.RUNNING
    run.started_at = datetime.now(tz=timezone.utc)
    if store:
        store.save(run)

    try:
        result_summary = analysis_fn(run, **kwargs)
        run.status = RunStatus.COMPLETED
        run.result_summary = result_summary
    except AnalysisError as exc:
        run.status = RunStatus.FAILED
        run.error_message = str(exc)
        run.error_type = exc.error_type
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.error_message = f"Unexpected error: {exc}"
        run.error_type = "unexpected_error"

    run.completed_at = datetime.now(tz=timezone.utc)
    if run.started_at:
        delta = run.completed_at - run.started_at
        run.duration_ms = int(delta.total_seconds() * 1000)

    if store:
        store.save(run)
    return run


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_run_manifest(run: AnalysisRun, base_dir: str | Path) -> Path:
    """Save run metadata as JSON to a run-specific subfolder."""
    run_dir = Path(base_dir) / run.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = run_dir / "run_manifest.json"
    manifest.write_text(
        json.dumps(run.provenance(), indent=2, default=str),
        encoding="utf-8",
    )
    return run_dir
