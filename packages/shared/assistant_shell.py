"""Global assistant shell service.

Powers the persistent assistant panel across all app stages.
Manages context chips, invocation logging, and stage-aware actions.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from .assistant_context import AssistantContext, WorkflowStage
from .interaction_patterns import (
    COPILOT_PANELS,
    CopilotAction,
    CopilotPanelSpec,
    Screen,
    get_checkpoints_for_screen,
    get_copilot_spec,
    get_fallback_for_screen,
)

logger = logging.getLogger(__name__)

SHELL_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Context chips — what the panel displays about current state
# ---------------------------------------------------------------------------

class ContextChip(BaseModel):
    """A single context chip displayed in the assistant panel."""

    key: str
    label: str
    value: str
    tooltip: str | None = None


def build_context_chips(ctx: AssistantContext) -> list[ContextChip]:
    """Generate context chips from the current assistant context."""
    chips: list[ContextChip] = []

    chips.append(ContextChip(
        key="project",
        label="Project",
        value=ctx.project_id,
    ))

    chips.append(ContextChip(
        key="methodology",
        label="Methodology",
        value=ctx.methodology.value,
    ))

    chips.append(ContextChip(
        key="stage",
        label="Stage",
        value=ctx.stage.value,
    ))

    if ctx.brief:
        chips.append(ContextChip(
            key="brief",
            label="Brief",
            value=ctx.brief.brief_id,
            tooltip=ctx.brief.objectives[:80] if ctx.brief.objectives else None,
        ))

    if ctx.questionnaire_ref:
        chips.append(ContextChip(
            key="questionnaire",
            label="Questionnaire",
            value=f"v{ctx.questionnaire_ref.version}",
            tooltip=ctx.questionnaire_ref.questionnaire_id,
        ))

    if ctx.mapping_ref:
        chips.append(ContextChip(
            key="mapping",
            label="Mapping",
            value=f"v{ctx.mapping_ref.version}",
            tooltip=f"data: {ctx.mapping_ref.data_file_hash[:12]}",
        ))

    if ctx.run_metadata:
        chips.append(ContextChip(
            key="run",
            label="Run",
            value=ctx.run_metadata.run_id,
            tooltip=ctx.run_metadata.run_type,
        ))

    return chips


# ---------------------------------------------------------------------------
# Context hashing — deterministic hash of the context for logging
# ---------------------------------------------------------------------------

def compute_context_hash(ctx: AssistantContext) -> str:
    """Compute a deterministic SHA-256 hash of the assistant context.

    Used to track which context was active during each invocation,
    enabling reproducibility and audit.
    """
    payload = ctx.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Invocation log — records every assistant call with context
# ---------------------------------------------------------------------------

class InvocationRecord(BaseModel):
    """One logged assistant invocation."""

    invocation_id: str
    timestamp: datetime
    project_id: str
    stage: WorkflowStage
    screen: Screen
    action: CopilotAction
    context_hash: str
    input_summary: str
    output_summary: str | None = None
    duration_ms: int | None = None
    status: str = "pending"  # pending, completed, failed


class InvocationLog:
    """In-memory invocation log. Will be backed by a database in later sprints."""

    def __init__(self) -> None:
        self._records: list[InvocationRecord] = []

    def record(
        self,
        *,
        invocation_id: str,
        ctx: AssistantContext,
        screen: Screen,
        action: CopilotAction,
        input_summary: str,
    ) -> InvocationRecord:
        """Log the start of an assistant invocation."""
        record = InvocationRecord(
            invocation_id=invocation_id,
            timestamp=datetime.now(tz=timezone.utc),
            project_id=ctx.project_id,
            stage=ctx.stage,
            screen=screen,
            action=action,
            context_hash=compute_context_hash(ctx),
            input_summary=input_summary,
        )
        self._records.append(record)
        logger.info(
            "Assistant invocation: id=%s screen=%s action=%s context_hash=%s",
            invocation_id,
            screen.value,
            action.value,
            record.context_hash,
        )
        return record

    def complete(
        self,
        invocation_id: str,
        output_summary: str,
        duration_ms: int,
    ) -> None:
        """Mark an invocation as completed."""
        for r in reversed(self._records):
            if r.invocation_id == invocation_id:
                r.output_summary = output_summary
                r.duration_ms = duration_ms
                r.status = "completed"
                return
        raise ValueError(f"Invocation {invocation_id!r} not found.")

    def fail(self, invocation_id: str, error: str) -> None:
        """Mark an invocation as failed."""
        for r in reversed(self._records):
            if r.invocation_id == invocation_id:
                r.output_summary = f"ERROR: {error}"
                r.status = "failed"
                return
        raise ValueError(f"Invocation {invocation_id!r} not found.")

    def get_by_project(self, project_id: str) -> list[InvocationRecord]:
        """Return all invocations for a project, newest first."""
        return [r for r in reversed(self._records) if r.project_id == project_id]

    def get_by_context_hash(self, context_hash: str) -> list[InvocationRecord]:
        """Return all invocations with a specific context hash."""
        return [r for r in self._records if r.context_hash == context_hash]

    @property
    def count(self) -> int:
        return len(self._records)


# ---------------------------------------------------------------------------
# Panel state — what the UI renders for a given screen + context
# ---------------------------------------------------------------------------

class PanelState(BaseModel):
    """Complete state for the assistant panel on a specific screen."""

    screen: Screen
    stage: WorkflowStage
    context_chips: list[ContextChip]
    available_actions: list[str]
    default_action: str
    has_checkpoint: bool
    checkpoints: list[dict[str, Any]] = Field(default_factory=list)
    has_fallback: bool
    context_hash: str


def get_panel_state(ctx: AssistantContext, screen: Screen) -> PanelState:
    """Build the full panel state for a screen given the current context."""
    spec = get_copilot_spec(screen)
    chips = build_context_chips(ctx)
    ctx_hash = compute_context_hash(ctx)

    checkpoints = get_checkpoints_for_screen(screen)
    fallbacks = get_fallback_for_screen(screen)

    return PanelState(
        screen=screen,
        stage=spec.workflow_stage,
        context_chips=chips,
        available_actions=[a.value for a in spec.available_actions],
        default_action=spec.default_action.value,
        has_checkpoint=len(checkpoints) > 0,
        checkpoints=[
            {"id": cp.checkpoint_id, "label": cp.label, "severity": cp.severity.value}
            for cp in checkpoints
        ],
        has_fallback=len(fallbacks) > 0,
        context_hash=ctx_hash,
    )
