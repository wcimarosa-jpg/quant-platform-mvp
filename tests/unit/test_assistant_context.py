"""Contract tests for AssistantContext (P00-01).

These tests verify that:
1. The schema includes all required fields.
2. Stage-gate validation rejects incomplete contexts.
3. Valid contexts pass for every stage.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from packages.shared.assistant_context import (
    CONTEXT_SCHEMA_VERSION,
    AssistantContext,
    BriefContext,
    ContextValidationError,
    MappingVersionRef,
    Methodology,
    QuestionnaireVersionRef,
    RunMetadata,
    WorkflowStage,
    validate_for_stage,
)

NOW = datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures — progressively richer contexts
# ---------------------------------------------------------------------------

def _brief_ctx() -> BriefContext:
    return BriefContext(
        brief_id="brief-001",
        objectives="Understand brand health",
        audience="US adults 18-54",
        category="snack bars",
        uploaded_at=NOW,
    )


def _qre_ref() -> QuestionnaireVersionRef:
    return QuestionnaireVersionRef(
        questionnaire_id="qre-001",
        version=1,
        section_ids=["screener", "attitudes", "brand_perceptions"],
    )


def _mapping_ref() -> MappingVersionRef:
    return MappingVersionRef(
        mapping_id="map-001",
        version=1,
        data_file_hash="sha256:abc123",
    )


def _run_metadata() -> RunMetadata:
    return RunMetadata(
        run_id="run-001",
        run_type="crosstabs",
        started_at=NOW,
        questionnaire_version=1,
        mapping_version=1,
    )


def _full_context(stage: WorkflowStage) -> AssistantContext:
    return AssistantContext(
        project_id="proj-001",
        stage=stage,
        methodology=Methodology.SEGMENTATION,
        brief=_brief_ctx(),
        selected_sections=["screener", "attitudes", "brand_perceptions"],
        questionnaire_ref=_qre_ref(),
        mapping_ref=_mapping_ref(),
        run_metadata=_run_metadata(),
    )


# ---------------------------------------------------------------------------
# AC-1: Schema includes required fields
# ---------------------------------------------------------------------------

class TestSchemaFields:
    def test_schema_version_present(self):
        ctx = _full_context(WorkflowStage.BRIEF)
        assert ctx.schema_version == CONTEXT_SCHEMA_VERSION

    def test_project_id_required(self):
        with pytest.raises(Exception):
            AssistantContext(stage=WorkflowStage.BRIEF, methodology=Methodology.SEGMENTATION)

    def test_all_top_level_fields_exist(self):
        ctx = _full_context(WorkflowStage.ANALYSIS)
        assert ctx.project_id == "proj-001"
        assert ctx.brief is not None
        assert ctx.methodology == Methodology.SEGMENTATION
        assert len(ctx.selected_sections) == 3
        assert ctx.questionnaire_ref is not None
        assert ctx.mapping_ref is not None
        assert ctx.run_metadata is not None

    def test_wrong_schema_version_rejected(self):
        with pytest.raises(ValueError, match="Unsupported schema version"):
            AssistantContext(
                schema_version="0.0.0",
                project_id="proj-001",
                stage=WorkflowStage.BRIEF,
                methodology=Methodology.SEGMENTATION,
            )


# ---------------------------------------------------------------------------
# AC-2: Schema is documented and versioned
# ---------------------------------------------------------------------------

class TestVersioning:
    def test_version_string_is_semver(self):
        parts = CONTEXT_SCHEMA_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_default_version_matches_constant(self):
        ctx = AssistantContext(
            project_id="proj-001",
            stage=WorkflowStage.BRIEF,
            methodology=Methodology.SEGMENTATION,
        )
        assert ctx.schema_version == CONTEXT_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# AC-3: Contract tests verify required fields before assistant call execution
# ---------------------------------------------------------------------------

class TestStageGateValidation:
    def test_brief_stage_minimal(self):
        ctx = AssistantContext(
            project_id="proj-001",
            stage=WorkflowStage.BRIEF,
            methodology=Methodology.ATTITUDE_USAGE,
        )
        validate_for_stage(ctx)  # should not raise

    def test_questionnaire_stage_requires_brief_and_sections(self):
        ctx = AssistantContext(
            project_id="proj-001",
            stage=WorkflowStage.QUESTIONNAIRE,
            methodology=Methodology.SEGMENTATION,
        )
        with pytest.raises(ContextValidationError) as exc_info:
            validate_for_stage(ctx)
        assert "brief" in exc_info.value.missing
        assert "selected_sections" in exc_info.value.missing

    def test_questionnaire_stage_valid(self):
        ctx = AssistantContext(
            project_id="proj-001",
            stage=WorkflowStage.QUESTIONNAIRE,
            methodology=Methodology.SEGMENTATION,
            brief=_brief_ctx(),
            selected_sections=["screener", "attitudes"],
        )
        validate_for_stage(ctx)

    def test_mapping_stage_requires_questionnaire_ref(self):
        ctx = AssistantContext(
            project_id="proj-001",
            stage=WorkflowStage.MAPPING,
            methodology=Methodology.SEGMENTATION,
            brief=_brief_ctx(),
            selected_sections=["screener"],
        )
        with pytest.raises(ContextValidationError) as exc_info:
            validate_for_stage(ctx)
        assert "questionnaire_ref" in exc_info.value.missing

    def test_table_qa_requires_mapping_ref(self):
        ctx = AssistantContext(
            project_id="proj-001",
            stage=WorkflowStage.TABLE_QA,
            methodology=Methodology.SEGMENTATION,
            questionnaire_ref=_qre_ref(),
        )
        with pytest.raises(ContextValidationError) as exc_info:
            validate_for_stage(ctx)
        assert "mapping_ref" in exc_info.value.missing

    def test_analysis_requires_run_metadata(self):
        ctx = AssistantContext(
            project_id="proj-001",
            stage=WorkflowStage.ANALYSIS,
            methodology=Methodology.SEGMENTATION,
            questionnaire_ref=_qre_ref(),
            mapping_ref=_mapping_ref(),
        )
        with pytest.raises(ContextValidationError) as exc_info:
            validate_for_stage(ctx)
        assert "run_metadata" in exc_info.value.missing

    def test_analysis_stage_valid(self):
        ctx = _full_context(WorkflowStage.ANALYSIS)
        validate_for_stage(ctx)

    def test_reporting_stage_valid(self):
        ctx = _full_context(WorkflowStage.REPORTING)
        validate_for_stage(ctx)

    @pytest.mark.parametrize("stage", list(WorkflowStage))
    def test_full_context_passes_all_stages(self, stage: WorkflowStage):
        ctx = _full_context(stage)
        validate_for_stage(ctx)  # should not raise


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_selected_sections_treated_as_missing(self):
        ctx = AssistantContext(
            project_id="proj-001",
            stage=WorkflowStage.QUESTIONNAIRE,
            methodology=Methodology.SEGMENTATION,
            brief=_brief_ctx(),
            selected_sections=[],
        )
        with pytest.raises(ContextValidationError) as exc_info:
            validate_for_stage(ctx)
        assert "selected_sections" in exc_info.value.missing

    def test_extra_field_passthrough(self):
        ctx = AssistantContext(
            project_id="proj-001",
            stage=WorkflowStage.BRIEF,
            methodology=Methodology.SEGMENTATION,
            extra={"custom_flag": True},
        )
        assert ctx.extra["custom_flag"] is True

    def test_all_methodologies_constructable(self):
        for m in Methodology:
            ctx = AssistantContext(
                project_id="proj-001",
                stage=WorkflowStage.BRIEF,
                methodology=m,
            )
            assert ctx.methodology == m


# ---------------------------------------------------------------------------
# Fix 2: Version consistency checks
# ---------------------------------------------------------------------------

class TestVersionConsistency:
    def test_matching_versions_pass(self):
        ctx = _full_context(WorkflowStage.ANALYSIS)
        validate_for_stage(ctx)  # should not raise

    def test_mismatched_questionnaire_version_fails(self):
        ctx = AssistantContext(
            project_id="proj-001",
            stage=WorkflowStage.ANALYSIS,
            methodology=Methodology.SEGMENTATION,
            brief=_brief_ctx(),
            selected_sections=["screener"],
            questionnaire_ref=QuestionnaireVersionRef(
                questionnaire_id="qre-001", version=3,
                section_ids=["screener"],
            ),
            mapping_ref=_mapping_ref(),
            run_metadata=RunMetadata(
                run_id="run-001", run_type="kmeans", started_at=NOW,
                questionnaire_version=99,  # mismatch!
                mapping_version=1,
            ),
        )
        with pytest.raises(ContextValidationError) as exc_info:
            validate_for_stage(ctx)
        assert len(exc_info.value.inconsistencies) >= 1
        assert "questionnaire_version" in exc_info.value.inconsistencies[0]

    def test_mismatched_mapping_version_fails(self):
        ctx = AssistantContext(
            project_id="proj-001",
            stage=WorkflowStage.REPORTING,
            methodology=Methodology.SEGMENTATION,
            brief=_brief_ctx(),
            selected_sections=["screener"],
            questionnaire_ref=_qre_ref(),
            mapping_ref=MappingVersionRef(
                mapping_id="map-001", version=2, data_file_hash="sha256:abc",
            ),
            run_metadata=RunMetadata(
                run_id="run-001", run_type="report", started_at=NOW,
                questionnaire_version=1,
                mapping_version=99,  # mismatch!
            ),
        )
        with pytest.raises(ContextValidationError) as exc_info:
            validate_for_stage(ctx)
        assert len(exc_info.value.inconsistencies) >= 1
        assert "mapping_version" in exc_info.value.inconsistencies[0]

    def test_consistency_not_checked_for_brief_stage(self):
        """Version consistency only applies to ANALYSIS/REPORTING."""
        ctx = AssistantContext(
            project_id="proj-001",
            stage=WorkflowStage.BRIEF,
            methodology=Methodology.SEGMENTATION,
        )
        validate_for_stage(ctx)  # no error even without refs


class TestSerializationRoundTrip:
    def test_model_dump_and_validate(self):
        """#1: Ensure context survives JSON serialization round-trip."""
        ctx = _full_context(WorkflowStage.ANALYSIS)
        dumped = ctx.model_dump(mode="json")
        restored = AssistantContext.model_validate(dumped)
        assert restored.project_id == ctx.project_id
        assert restored.methodology == ctx.methodology
        assert restored.stage == ctx.stage
        assert restored.questionnaire_ref.version == ctx.questionnaire_ref.version
