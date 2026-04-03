"""Brief analyzer assistant mode.

Analyzes a parsed brief to produce a summary, identify gaps,
and propose assumptions for user confirmation. Accepted assumptions
merge into the generation context.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .brief_parser import BriefFields


class AssumptionStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Assumption(BaseModel):
    """One proposed assumption about a missing or ambiguous brief field."""

    assumption_id: str = Field(default_factory=lambda: f"asmp-{uuid.uuid4().hex[:8]}")
    field: str                  # which BriefFields field this addresses
    proposal: str               # the proposed value or clarification
    rationale: str              # why this assumption is reasonable
    source_reference: str       # what brief content supports this
    status: AssumptionStatus = AssumptionStatus.PENDING


class BriefAnalysis(BaseModel):
    """Complete analysis result for a parsed brief."""

    analysis_id: str = Field(default_factory=lambda: f"analysis-{uuid.uuid4().hex[:8]}")
    brief_id: str
    summary: str
    gaps: list[str]
    assumptions: list[Assumption]
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def pending_assumptions(self) -> list[Assumption]:
        return [a for a in self.assumptions if a.status == AssumptionStatus.PENDING]

    def accepted_assumptions(self) -> list[Assumption]:
        return [a for a in self.assumptions if a.status == AssumptionStatus.ACCEPTED]

    def all_resolved(self) -> bool:
        return len(self.pending_assumptions()) == 0


# ---------------------------------------------------------------------------
# Analyzer — deterministic heuristic analysis (no LLM call)
#
# In production, this will be replaced by an LLM-backed analyzer
# that uses the AssistantContext. For now, the heuristic version
# satisfies the contract and is fully testable.
# ---------------------------------------------------------------------------

_FIELD_LABELS = {
    "objectives": "Research Objectives",
    "audience": "Target Audience",
    "category": "Product Category",
    "geography": "Geographic Scope",
    "constraints": "Constraints / Requirements",
}

_DEFAULT_ASSUMPTIONS: dict[str, dict[str, str]] = {
    "audience": {
        "proposal": "General population adults 18+",
        "rationale": "No audience specified; defaulting to broad population for initial screening.",
    },
    "category": {
        "proposal": "General consumer products",
        "rationale": "No category specified; using broad category until brief is refined.",
    },
    "geography": {
        "proposal": "United States, nationally representative",
        "rationale": "No geography specified; defaulting to US national scope.",
    },
    "constraints": {
        "proposal": "LOI target: 15-20 minutes; no specific budget constraints noted",
        "rationale": "No constraints specified; using standard survey parameters.",
    },
}


def analyze_brief(brief_id: str, fields: BriefFields) -> BriefAnalysis:
    """Analyze a parsed brief: summarize, find gaps, propose assumptions."""

    # Build summary referencing actual brief content
    summary_parts = []
    if fields.objectives:
        summary_parts.append(f"This study aims to: {fields.objectives}")
    if fields.audience:
        summary_parts.append(f"Target audience: {fields.audience}")
    if fields.category:
        summary_parts.append(f"Category: {fields.category}")
    if fields.geography:
        summary_parts.append(f"Geography: {fields.geography}")
    if fields.constraints:
        summary_parts.append(f"Key constraints: {fields.constraints}")

    if not summary_parts:
        summary = "Brief is empty. All required fields need to be provided."
    else:
        summary = " ".join(summary_parts)

    # Identify gaps
    gaps: list[str] = []
    for field_name in fields.missing_fields():
        label = _FIELD_LABELS.get(field_name, field_name)
        gaps.append(f"{label} is not specified in the brief.")

    # Propose assumptions for missing fields
    assumptions: list[Assumption] = []
    for field_name in fields.missing_fields():
        default = _DEFAULT_ASSUMPTIONS.get(field_name)
        if default:
            # Reference what IS in the brief as source context
            source_ref = _build_source_reference(fields, field_name)
            assumptions.append(Assumption(
                field=field_name,
                proposal=default["proposal"],
                rationale=default["rationale"],
                source_reference=source_ref,
            ))

    return BriefAnalysis(
        brief_id=brief_id,
        summary=summary,
        gaps=gaps,
        assumptions=assumptions,
    )


def _build_source_reference(fields: BriefFields, missing_field: str) -> str:
    """Build a source reference string from available brief content."""
    present = []
    if fields.objectives:
        present.append(f"objectives: '{fields.objectives[:60]}...'")
    if fields.audience:
        present.append(f"audience: '{fields.audience[:60]}'")
    if fields.category:
        present.append(f"category: '{fields.category[:60]}'")
    if present:
        return f"Brief provides {', '.join(present)} but {missing_field} is not specified."
    return "Brief content is minimal; no related fields to reference."


# ---------------------------------------------------------------------------
# Assumption resolution — accept/reject with merge into fields
# ---------------------------------------------------------------------------

def resolve_assumption(
    analysis: BriefAnalysis,
    assumption_id: str,
    decision: AssumptionStatus,
) -> Assumption:
    """Accept or reject a specific assumption."""
    if decision == AssumptionStatus.PENDING:
        raise ValueError("Cannot set status back to pending.")
    for a in analysis.assumptions:
        if a.assumption_id == assumption_id:
            a.status = decision
            return a
    raise ValueError(f"Assumption {assumption_id!r} not found.")


def apply_accepted_assumptions(fields: BriefFields, analysis: BriefAnalysis) -> BriefFields:
    """Merge accepted assumptions into brief fields, returning the updated fields."""
    for a in analysis.accepted_assumptions():
        if hasattr(fields, a.field) and getattr(fields, a.field) is None:
            setattr(fields, a.field, a.proposal)
    return fields
