"""Assistant context contract v1.

Every assistant call in the platform receives an AssistantContext instance.
This module defines the canonical schema, version, and validation logic.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

CONTEXT_SCHEMA_VERSION = "1.0.0"


class Methodology(str, Enum):
    ATTITUDE_USAGE = "attitude_usage"
    SEGMENTATION = "segmentation"
    DRIVERS = "drivers"
    CONCEPT_MONADIC = "concept_monadic"
    CREATIVE_MONADIC = "creative_monadic"
    BRAND_EQUITY_TRACKER = "brand_equity_tracker"
    MAXDIFF = "maxdiff"
    TURF = "turf"


class WorkflowStage(str, Enum):
    BRIEF = "brief"
    QUESTIONNAIRE = "questionnaire"
    MAPPING = "mapping"
    TABLE_QA = "table_qa"
    ANALYSIS = "analysis"
    REPORTING = "reporting"


class BriefContext(BaseModel):
    """Extracted brief metadata available after ingestion."""

    brief_id: str
    objectives: str
    audience: str | None = None
    category: str | None = None
    geography: str | None = None
    constraints: str | None = None
    uploaded_at: datetime


class QuestionnaireVersionRef(BaseModel):
    """Pointer to a specific questionnaire version."""

    questionnaire_id: str
    version: int
    section_ids: list[str] = Field(default_factory=list)


class MappingVersionRef(BaseModel):
    """Pointer to a specific mapping version."""

    mapping_id: str
    version: int
    data_file_hash: str


class RunMetadata(BaseModel):
    """Metadata for an analysis or table-generation run."""

    run_id: str
    run_type: str
    started_at: datetime
    questionnaire_version: int
    mapping_version: int
    parameters: dict[str, Any] = Field(default_factory=dict)


class AssistantContext(BaseModel):
    """Canonical context packet passed to every assistant invocation.

    Fields are progressively populated as the workflow advances.
    The ``validate_for_stage`` method enforces stage-specific requirements.
    """

    schema_version: str = CONTEXT_SCHEMA_VERSION

    # Always required
    project_id: str
    stage: WorkflowStage
    methodology: Methodology

    # Progressive — populated as workflow advances
    brief: BriefContext | None = None
    selected_sections: list[str] = Field(default_factory=list)
    questionnaire_ref: QuestionnaireVersionRef | None = None
    mapping_ref: MappingVersionRef | None = None
    run_metadata: RunMetadata | None = None

    # Extensible slot for stage-specific extras
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_schema_version(self) -> "AssistantContext":
        if self.schema_version != CONTEXT_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported schema version {self.schema_version!r}; "
                f"expected {CONTEXT_SCHEMA_VERSION!r}"
            )
        return self


# ---------------------------------------------------------------------------
# Stage-gate validation
# ---------------------------------------------------------------------------

_STAGE_REQUIREMENTS: dict[WorkflowStage, list[str]] = {
    WorkflowStage.BRIEF: ["project_id", "methodology"],
    WorkflowStage.QUESTIONNAIRE: ["project_id", "methodology", "brief", "selected_sections"],
    WorkflowStage.MAPPING: ["project_id", "methodology", "questionnaire_ref"],
    WorkflowStage.TABLE_QA: ["project_id", "methodology", "questionnaire_ref", "mapping_ref"],
    WorkflowStage.ANALYSIS: ["project_id", "methodology", "questionnaire_ref", "mapping_ref", "run_metadata"],
    WorkflowStage.REPORTING: ["project_id", "methodology", "questionnaire_ref", "mapping_ref", "run_metadata"],
}


class ContextValidationError(Exception):
    """Raised when the context is insufficient for the requested stage."""

    def __init__(self, stage: WorkflowStage, missing: list[str]) -> None:
        self.stage = stage
        self.missing = missing
        super().__init__(f"Stage {stage.value!r} requires: {', '.join(missing)}")


def validate_for_stage(ctx: AssistantContext) -> None:
    """Raise ``ContextValidationError`` if required fields are missing for the context's stage."""
    missing: list[str] = []
    for field_name in _STAGE_REQUIREMENTS.get(ctx.stage, []):
        value = getattr(ctx, field_name, None)
        if value is None:
            missing.append(field_name)
        elif isinstance(value, list) and len(value) == 0:
            missing.append(field_name)
    if missing:
        raise ContextValidationError(ctx.stage, missing)
