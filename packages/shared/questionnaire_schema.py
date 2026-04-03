"""Questionnaire schema — the canonical output structure.

Defines Question, Section, and Questionnaire models that all
generation, editing, validation, and export code operates on.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .assistant_context import Methodology


class QuestionType(str, Enum):
    SINGLE_SELECT = "single_select"
    MULTI_SELECT = "multi_select"
    LIKERT_SCALE = "likert_scale"
    NUMERIC = "numeric"
    OPEN_ENDED = "open_ended"
    MAXDIFF_TASK = "maxdiff_task"
    RANKING = "ranking"


class ResponseOption(BaseModel):
    """One response option for a closed-ended question."""

    code: int
    label: str
    terminates: bool = False


class Question(BaseModel):
    """One question in a questionnaire section."""

    question_id: str
    question_text: str
    question_type: QuestionType
    var_name: str
    response_options: list[ResponseOption] = Field(default_factory=list)
    scale_points: int | None = None
    scale_labels: dict[int, str] | None = None
    required: bool = True
    logic: str | None = None  # skip/display logic description


class Section(BaseModel):
    """One section of a questionnaire."""

    section_id: str
    section_type: str
    label: str
    order: int
    questions: list[Question]
    metadata: dict[str, Any] = Field(default_factory=dict)


class Questionnaire(BaseModel):
    """Complete questionnaire output."""

    questionnaire_id: str = Field(default_factory=lambda: f"qre-{uuid.uuid4().hex[:8]}")
    project_id: str
    methodology: str
    version: int = 1
    sections: list[Section]
    total_questions: int = 0
    estimated_loi_minutes: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    # Generation provenance
    draft_id: str | None = None
    brief_id: str | None = None
    context_hash: str | None = None

    def model_post_init(self, __context: Any) -> None:
        self.total_questions = sum(len(s.questions) for s in self.sections)

    def get_section(self, section_type: str) -> Section | None:
        for s in self.sections:
            if s.section_type == section_type:
                return s
        return None

    def section_types(self) -> list[str]:
        return [s.section_type for s in self.sections]
