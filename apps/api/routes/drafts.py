"""Methodology and section selector API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from packages.shared.assistant_context import Methodology
from packages.shared.draft_config import DraftConfig, DraftStore
from packages.shared.section_taxonomy import get_all_methodologies, get_matrix

router = APIRouter(prefix="/drafts", tags=["drafts"])

_store = DraftStore()


@router.get("/methodologies")
def list_methodologies() -> dict[str, Any]:
    """Return all supported methodologies for the selector UI."""
    return {"methodologies": get_all_methodologies()}


@router.get("/methodologies/{methodology}/sections")
def get_sections(methodology: str) -> dict[str, Any]:
    """Return available sections for a methodology."""
    try:
        meth = Methodology(methodology)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown methodology: {methodology}")
    matrix = get_matrix(meth)
    return {
        "methodology": meth.value,
        "label": matrix.label,
        "default_loi": list(matrix.default_loi_minutes),
        "sections": matrix.for_ui(),
    }


class CreateDraftRequest(BaseModel):
    project_id: str
    methodology: str


@router.post("/")
def create_draft(body: CreateDraftRequest) -> dict[str, Any]:
    """Create a new draft with methodology and all sections pre-selected."""
    try:
        meth = Methodology(body.methodology)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown methodology: {body.methodology}")

    draft = _store.create(body.project_id, meth)
    return _draft_response(draft)


@router.get("/{draft_id}")
def get_draft(draft_id: str) -> dict[str, Any]:
    """Get a draft's current state."""
    draft = _store.get(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")
    return _draft_response(draft)


class UpdateMethodologyRequest(BaseModel):
    methodology: str


@router.patch("/{draft_id}/methodology")
def update_methodology(draft_id: str, body: UpdateMethodologyRequest) -> dict[str, Any]:
    """Change the methodology for a draft. Resets sections to defaults."""
    draft = _store.get(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")
    try:
        meth = Methodology(body.methodology)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown methodology: {body.methodology}")

    draft.update_methodology(meth)
    return _draft_response(draft)


class UpdateSectionsRequest(BaseModel):
    selected_sections: list[str]


@router.patch("/{draft_id}/sections")
def update_sections(draft_id: str, body: UpdateSectionsRequest) -> dict[str, Any]:
    """Update selected sections for a draft."""
    draft = _store.get(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")

    errors = draft.update_sections(body.selected_sections)
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})

    return _draft_response(draft)


@router.get("/{draft_id}/generation-config")
def get_generation_config(draft_id: str) -> dict[str, Any]:
    """Get the finalized generation config for the engine."""
    draft = _store.get(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")
    return draft.for_generation()


def _draft_response(draft: DraftConfig) -> dict[str, Any]:
    return {
        "draft_id": draft.draft_id,
        "project_id": draft.project_id,
        "methodology": draft.methodology.value,
        "selected_sections": draft.selected_sections,
        "section_options": draft.get_section_options(),
        "updated_at": draft.updated_at.isoformat(),
    }
