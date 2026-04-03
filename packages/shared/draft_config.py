"""Draft configuration — persists methodology and section selections.

Stores the user's methodology choice and selected sections as a
draft that feeds into questionnaire generation.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from .assistant_context import Methodology
from .section_taxonomy import (
    METHODOLOGY_MATRIX,
    get_all_methodologies,
    get_matrix,
    validate_section_selection,
)


class DraftConfig(BaseModel):
    """Persisted draft for a project's generation configuration."""

    draft_id: str = Field(default_factory=lambda: f"draft-{uuid.uuid4().hex[:8]}")
    project_id: str
    methodology: Methodology
    selected_sections: list[str]
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def update_methodology(self, methodology: Methodology) -> list[str]:
        """Change methodology and auto-select required sections. Returns validation errors."""
        self.methodology = methodology
        matrix = get_matrix(methodology)
        # Auto-select all sections (required ones can't be deselected)
        self.selected_sections = [st.value for st in matrix.section_order]
        self.updated_at = datetime.now(tz=timezone.utc)
        return []

    def update_sections(self, selected: list[str]) -> list[str]:
        """Update section selection. Returns validation errors if any."""
        errors = validate_section_selection(self.methodology, selected)
        if not errors:
            self.selected_sections = selected
            self.updated_at = datetime.now(tz=timezone.utc)
        return errors

    def get_section_options(self) -> list[dict[str, Any]]:
        """Return section options for the UI, reflecting the current methodology."""
        matrix = get_matrix(self.methodology)
        options = matrix.for_ui()
        # Mark which ones are currently selected
        selected_set = set(self.selected_sections)
        for opt in options:
            opt["selected"] = opt["section_type"] in selected_set
        return options

    def for_generation(self) -> dict[str, Any]:
        """Return the config payload for the generation engine."""
        matrix = get_matrix(self.methodology)
        return {
            "draft_id": self.draft_id,
            "project_id": self.project_id,
            "methodology": self.methodology.value,
            "sections": matrix.for_generation(self.selected_sections),
            "loi_range": list(matrix.default_loi_minutes),
        }


class DraftStore:
    """In-memory draft store. Will be backed by database later."""

    def __init__(self) -> None:
        self._drafts: dict[str, DraftConfig] = {}

    def create(self, project_id: str, methodology: Methodology) -> DraftConfig:
        """Create a new draft with all sections pre-selected."""
        matrix = get_matrix(methodology)
        draft = DraftConfig(
            project_id=project_id,
            methodology=methodology,
            selected_sections=[st.value for st in matrix.section_order],
        )
        self._drafts[draft.draft_id] = draft
        return draft

    def get(self, draft_id: str) -> DraftConfig | None:
        return self._drafts.get(draft_id)

    def get_by_project(self, project_id: str) -> DraftConfig | None:
        """Return the latest draft for a project."""
        for draft in reversed(list(self._drafts.values())):
            if draft.project_id == project_id:
                return draft
        return None

    @property
    def count(self) -> int:
        return len(self._drafts)
