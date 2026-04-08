"""Brief analysis API routes."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apps.api.auth_deps import CurrentUser
from apps.api.resource_auth import get_ownership, record_ownership, require_owner
from packages.shared.brief_analyzer import (
    AssumptionStatus,
    BriefAnalysis,
    analyze_brief,
    apply_accepted_assumptions,
    resolve_assumption,
)
from packages.shared.brief_parser import BriefFields

# Re-use the in-memory stores from briefs route
from apps.api.routes.briefs import _briefs

router = APIRouter(prefix="/briefs", tags=["brief-analysis"])

# In-memory analysis store
_analyses: dict[str, BriefAnalysis] = {}


@router.post("/{brief_id}/analyze")
def analyze(brief_id: str, user: CurrentUser) -> dict[str, Any]:
    """Run the brief analyzer and return summary, gaps, and assumptions."""
    require_owner(brief_id, user)
    fields = _briefs.get(brief_id)
    if not fields:
        raise HTTPException(status_code=404, detail="Brief not found.")

    analysis = analyze_brief(brief_id, fields)
    _analyses[analysis.analysis_id] = analysis
    # Inherit ownership from the parent brief
    brief_meta = get_ownership(brief_id) or {}
    record_ownership(
        analysis.analysis_id,
        owner_id=user.sub,
        project_id=brief_meta.get("project_id", ""),
    )

    return {
        "analysis_id": analysis.analysis_id,
        "brief_id": brief_id,
        "summary": analysis.summary,
        "gaps": analysis.gaps,
        "assumptions": [
            {
                "assumption_id": a.assumption_id,
                "field": a.field,
                "proposal": a.proposal,
                "rationale": a.rationale,
                "source_reference": a.source_reference,
                "status": a.status.value,
            }
            for a in analysis.assumptions
        ],
        "all_resolved": analysis.all_resolved(),
    }


class AssumptionDecision(BaseModel):
    decision: Literal["accepted", "rejected"]


@router.patch("/analysis/{analysis_id}/assumptions/{assumption_id}")
def resolve(analysis_id: str, assumption_id: str, body: AssumptionDecision, user: CurrentUser) -> dict[str, Any]:
    """Accept or reject a specific assumption."""
    require_owner(analysis_id, user)
    analysis = _analyses.get(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    status = AssumptionStatus(body.decision)
    try:
        assumption = resolve_assumption(analysis, assumption_id, status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "assumption_id": assumption.assumption_id,
        "field": assumption.field,
        "status": assumption.status.value,
        "all_resolved": analysis.all_resolved(),
    }


@router.post("/analysis/{analysis_id}/apply")
def apply_assumptions(analysis_id: str, user: CurrentUser) -> dict[str, Any]:
    """Apply all accepted assumptions to the brief fields."""
    require_owner(analysis_id, user)
    analysis = _analyses.get(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    # Re-verify ownership of the underlying brief — apply mutates it
    require_owner(analysis.brief_id, user)
    fields = _briefs.get(analysis.brief_id)
    if not fields:
        raise HTTPException(status_code=404, detail="Brief not found.")

    if not analysis.all_resolved():
        raise HTTPException(
            status_code=400,
            detail=f"{len(analysis.pending_assumptions())} assumption(s) still pending.",
        )

    apply_accepted_assumptions(fields, analysis)

    return {
        "brief_id": analysis.brief_id,
        "objectives": fields.objectives,
        "audience": fields.audience,
        "category": fields.category,
        "geography": fields.geography,
        "constraints": fields.constraints,
        "is_complete": fields.is_complete(),
        "accepted_count": len(analysis.accepted_assumptions()),
    }
