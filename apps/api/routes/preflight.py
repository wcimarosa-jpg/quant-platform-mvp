"""Preflight gate API route."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from packages.shared.assistant_context import Methodology
from packages.shared.preflight import run_preflight

from apps.api.routes.briefs import _briefs

router = APIRouter(prefix="/preflight", tags=["preflight"])


@router.get("/{brief_id}")
def preflight_check(brief_id: str, methodology: str | None = None) -> dict[str, Any]:
    """Run preflight checks for a brief before generation."""
    fields = _briefs.get(brief_id)
    if not fields:
        raise HTTPException(status_code=404, detail="Brief not found.")

    meth = None
    if methodology:
        try:
            meth = Methodology(methodology)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown methodology: {methodology}")

    result = run_preflight(fields, methodology=meth)

    return {
        "brief_id": brief_id,
        "can_generate": result.can_generate,
        "blocking_count": result.blocking_count,
        "warning_count": result.warning_count,
        "checks": result.for_ui(),
    }
