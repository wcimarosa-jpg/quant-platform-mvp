"""Event logging and provenance foundation.

Captures user and assistant events with project and artifact references.
All events are immutable once recorded. Queryable by project and run.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event types — the universe of trackable actions
# ---------------------------------------------------------------------------

class EventCategory(str, Enum):
    PROJECT = "project"
    BRIEF = "brief"
    QUESTIONNAIRE = "questionnaire"
    DATA = "data"
    MAPPING = "mapping"
    ANALYSIS = "analysis"
    EXPORT = "export"
    ASSISTANT = "assistant"


class EventAction(str, Enum):
    # Project
    PROJECT_CREATED = "project.created"
    PROJECT_UPDATED = "project.updated"

    # Brief
    BRIEF_UPLOADED = "brief.uploaded"
    BRIEF_PARSED = "brief.parsed"
    BRIEF_UPDATED = "brief.updated"

    # Questionnaire
    QUESTIONNAIRE_GENERATED = "questionnaire.generated"
    QUESTIONNAIRE_UPDATED = "questionnaire.updated"
    QUESTIONNAIRE_PUBLISHED = "questionnaire.published"
    SECTION_REGENERATED = "section.regenerated"

    # Data
    DATA_UPLOADED = "data.uploaded"
    DATA_PROFILED = "data.profiled"

    # Mapping
    MAPPING_GENERATED = "mapping.generated"
    MAPPING_UPDATED = "mapping.updated"
    MAPPING_LOCKED = "mapping.locked"

    # Analysis
    RUN_QUEUED = "run.queued"
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"

    # Export
    EXPORT_GENERATED = "export.generated"
    EXPORT_DOWNLOADED = "export.downloaded"

    # Assistant
    ASSISTANT_INVOKED = "assistant.invoked"
    ASSISTANT_COMPLETED = "assistant.completed"
    ASSISTANT_FAILED = "assistant.failed"


def _category_for_action(action: EventAction) -> EventCategory:
    prefix = action.value.split(".")[0]
    mapping = {
        "project": EventCategory.PROJECT,
        "brief": EventCategory.BRIEF,
        "questionnaire": EventCategory.QUESTIONNAIRE,
        "section": EventCategory.QUESTIONNAIRE,
        "data": EventCategory.DATA,
        "mapping": EventCategory.MAPPING,
        "run": EventCategory.ANALYSIS,
        "export": EventCategory.EXPORT,
        "assistant": EventCategory.ASSISTANT,
    }
    if prefix not in mapping:
        raise ValueError(f"No category mapping for action prefix: {prefix!r}")
    return mapping[prefix]


# ---------------------------------------------------------------------------
# Event record
# ---------------------------------------------------------------------------

class ArtifactRef(BaseModel):
    """Reference to a versioned artifact."""

    model_config = ConfigDict(frozen=True)

    artifact_type: str          # "questionnaire", "mapping", "data_file", "run", "export"
    artifact_id: str
    version: int | None = None


class AssistantMetadata(BaseModel):
    """Prompt-context metadata for assistant actions."""

    model_config = ConfigDict(frozen=True)

    context_hash: str
    action: str
    screen: str
    input_summary: str
    output_summary: str | None = None
    duration_ms: int | None = None
    model: str | None = None


class Event(BaseModel):
    """One immutable event in the provenance log."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    project_id: str
    category: EventCategory
    action: EventAction
    actor: str                  # "user" or "assistant" or specific user ID
    description: str

    # Artifact references — what was created/modified
    artifacts: list[ArtifactRef] = Field(default_factory=list)

    # Run reference — links event to a specific analysis run
    run_id: str | None = None

    # Assistant-specific metadata (AC-2)
    assistant_metadata: AssistantMetadata | None = None

    # Extensible
    extra: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Event store — in-memory, will be backed by database in later sprints
# ---------------------------------------------------------------------------

class EventStore:
    """Append-only event store with project and run queries."""

    def __init__(self) -> None:
        self._events: list[Event] = []
        self._next_id: int = 1

    def emit(
        self,
        *,
        project_id: str,
        action: EventAction,
        actor: str,
        description: str,
        artifacts: list[ArtifactRef] | None = None,
        run_id: str | None = None,
        assistant_metadata: AssistantMetadata | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Event:
        """Record an event. Returns the created event."""
        event = Event(
            event_id=f"evt-{self._next_id:06d}",
            project_id=project_id,
            category=_category_for_action(action),
            action=action,
            actor=actor,
            description=description,
            artifacts=artifacts or [],
            run_id=run_id,
            assistant_metadata=assistant_metadata,
            extra=extra or {},
        )
        self._events.append(event)
        self._next_id += 1

        logger.info(
            "Event: id=%s project=%s action=%s actor=%s",
            event.event_id,
            event.project_id,
            event.action.value,
            event.actor,
        )
        return event

    # ------------------------------------------------------------------
    # Queries (AC-3)
    # ------------------------------------------------------------------

    def by_project(self, project_id: str, limit: int = 100) -> list[Event]:
        """Return events for a project, newest first."""
        return [
            e for e in reversed(self._events) if e.project_id == project_id
        ][:limit]

    def by_run(self, run_id: str) -> list[Event]:
        """Return all events linked to a specific analysis run."""
        return [e for e in self._events if e.run_id == run_id]

    def by_action(self, action: EventAction, project_id: str | None = None) -> list[Event]:
        """Return events of a specific action type, optionally filtered by project."""
        results = [e for e in self._events if e.action == action]
        if project_id:
            results = [e for e in results if e.project_id == project_id]
        return results

    def by_category(self, category: EventCategory, project_id: str | None = None) -> list[Event]:
        """Return events of a specific category."""
        results = [e for e in self._events if e.category == category]
        if project_id:
            results = [e for e in results if e.project_id == project_id]
        return results

    def by_artifact(self, artifact_id: str) -> list[Event]:
        """Return events that reference a specific artifact."""
        return [
            e for e in self._events
            if any(a.artifact_id == artifact_id for a in e.artifacts)
        ]

    @property
    def count(self) -> int:
        return len(self._events)

    def all(self, limit: int = 500) -> list[Event]:
        """Return all events, newest first."""
        return list(reversed(self._events))[:limit]
