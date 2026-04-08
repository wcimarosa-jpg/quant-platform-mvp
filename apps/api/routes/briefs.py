"""Brief ingestion API routes."""

from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from apps.api.auth_deps import CurrentUser
from apps.api.resource_auth import record_ownership, require_owner
from packages.shared.brief_parser import (
    BriefFields,
    BriefParseError,
    ingest_brief,
)

router = APIRouter(prefix="/briefs", tags=["briefs"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

# In-memory store — will be replaced by workspace + DB in later sprints
_briefs: dict[str, BriefFields] = {}


@router.post("/upload")
async def upload_brief(project_id: str, file: UploadFile, user: CurrentUser) -> dict[str, Any]:
    """Upload and parse a research brief file."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    content = await file.read()

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum 10 MB.")

    # Sanitize filename — strip path components
    safe_filename = os.path.basename(file.filename)

    try:
        fields = ingest_brief(content, safe_filename)
    except BriefParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    brief_id = f"brief-{uuid.uuid4().hex[:8]}"
    _briefs[brief_id] = fields
    record_ownership(brief_id, owner_id=user.sub, project_id=project_id)

    return {
        "brief_id": brief_id,
        "project_id": project_id,
        "source_filename": fields.source_filename,
        "source_format": fields.source_format,
        "extracted_fields": {
            "objectives": fields.objectives,
            "audience": fields.audience,
            "category": fields.category,
            "geography": fields.geography,
            "constraints": fields.constraints,
        },
        "missing_fields": fields.missing_fields(),
        "is_complete": fields.is_complete(),
    }


@router.get("/{brief_id}")
def get_brief(brief_id: str, user: CurrentUser) -> dict[str, Any]:
    """Get a brief's extracted fields."""
    fields = _briefs.get(brief_id)
    if not fields:
        raise HTTPException(status_code=404, detail="Brief not found.")
    require_owner(brief_id, user)

    raw_text = fields.raw_text
    truncated = len(raw_text) > 500
    return {
        "brief_id": brief_id,
        "objectives": fields.objectives,
        "audience": fields.audience,
        "category": fields.category,
        "geography": fields.geography,
        "constraints": fields.constraints,
        "raw_text": raw_text[:500],
        "raw_text_truncated": truncated,
        "missing_fields": fields.missing_fields(),
        "is_complete": fields.is_complete(),
    }


class BriefUpdate(BaseModel):
    """Typed partial-update model for brief fields."""

    objectives: str | None = None
    audience: str | None = None
    category: str | None = None
    geography: str | None = None
    constraints: str | None = None


@router.patch("/{brief_id}")
def update_brief(brief_id: str, updates: BriefUpdate, user: CurrentUser) -> dict[str, Any]:
    """Manually edit extracted brief fields before saving."""
    fields = _briefs.get(brief_id)
    if not fields:
        raise HTTPException(status_code=404, detail="Brief not found.")
    require_owner(brief_id, user)

    for key, value in updates.model_dump(exclude_unset=True).items():
        setattr(fields, key, value)

    return {
        "brief_id": brief_id,
        "objectives": fields.objectives,
        "audience": fields.audience,
        "category": fields.category,
        "geography": fields.geography,
        "constraints": fields.constraints,
        "missing_fields": fields.missing_fields(),
        "is_complete": fields.is_complete(),
    }
