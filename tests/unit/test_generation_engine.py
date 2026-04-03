"""Contract tests for questionnaire generation engine (P03-02).

AC-1: Generation payload includes assistant context contract.
AC-2: Only selected sections are generated.
AC-3: Questionnaire structure conforms to schema and section order.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from packages.shared.assistant_context import (
    AssistantContext,
    BriefContext,
    ContextValidationError,
    Methodology,
    WorkflowStage,
)
from packages.shared.draft_config import DraftConfig, DraftStore
from packages.shared.questionnaire_schema import (
    Question,
    Questionnaire,
    Section,
)
from packages.shared.section_taxonomy import get_matrix
from packages.survey_generation.engine import GenerationError, generate_questionnaire

NOW = datetime.now(tz=timezone.utc)


def _brief() -> BriefContext:
    return BriefContext(
        brief_id="brief-001",
        objectives="Understand brand health for KIND Bars",
        audience="US adults 18-54",
        category="premium snack bars",
        geography="United States",
        uploaded_at=NOW,
    )


def _ctx(methodology: Methodology = Methodology.SEGMENTATION) -> AssistantContext:
    return AssistantContext(
        project_id="proj-001",
        stage=WorkflowStage.QUESTIONNAIRE,
        methodology=methodology,
        brief=_brief(),
        selected_sections=["screener", "attitudes", "demographics"],
    )


def _draft(methodology: Methodology = Methodology.SEGMENTATION) -> DraftConfig:
    store = DraftStore()
    return store.create("proj-001", methodology)


# ---------------------------------------------------------------------------
# AC-1: Generation payload includes assistant context contract
# ---------------------------------------------------------------------------

class TestContextContract:
    def test_generation_requires_valid_context(self):
        draft = _draft()
        ctx = _ctx()
        qre = generate_questionnaire(draft, ctx)
        assert qre.context_hash is not None
        assert len(qre.context_hash) == 16

    def test_generation_fails_without_brief(self):
        draft = _draft()
        ctx = AssistantContext(
            project_id="proj-001",
            stage=WorkflowStage.QUESTIONNAIRE,
            methodology=Methodology.SEGMENTATION,
            # No brief — should fail stage validation
        )
        with pytest.raises(ContextValidationError):
            generate_questionnaire(draft, ctx)

    def test_generation_fails_without_sections(self):
        draft = _draft()
        ctx = AssistantContext(
            project_id="proj-001",
            stage=WorkflowStage.QUESTIONNAIRE,
            methodology=Methodology.SEGMENTATION,
            brief=_brief(),
            selected_sections=[],  # empty
        )
        with pytest.raises(ContextValidationError):
            generate_questionnaire(draft, ctx)

    def test_context_hash_stored_in_output(self):
        draft = _draft()
        ctx = _ctx()
        qre = generate_questionnaire(draft, ctx)
        assert qre.context_hash is not None

    def test_brief_id_stored_in_output(self):
        draft = _draft()
        ctx = _ctx()
        qre = generate_questionnaire(draft, ctx)
        assert qre.brief_id == "brief-001"

    def test_draft_id_stored_in_output(self):
        draft = _draft()
        ctx = _ctx()
        qre = generate_questionnaire(draft, ctx)
        assert qre.draft_id == draft.draft_id


# ---------------------------------------------------------------------------
# AC-2: Only selected sections are generated
# ---------------------------------------------------------------------------

class TestSelectedSectionsOnly:
    def test_all_sections_generated_when_all_selected(self):
        draft = _draft(Methodology.SEGMENTATION)
        ctx = _ctx(Methodology.SEGMENTATION)
        qre = generate_questionnaire(draft, ctx)
        matrix = get_matrix(Methodology.SEGMENTATION)
        assert len(qre.sections) == len(matrix.section_order)

    def test_only_required_sections_when_others_deselected(self):
        draft = _draft(Methodology.SEGMENTATION)
        matrix = get_matrix(Methodology.SEGMENTATION)
        required_only = [st.value for st in matrix.required_sections()]
        draft.update_sections(required_only)
        ctx = _ctx(Methodology.SEGMENTATION)
        qre = generate_questionnaire(draft, ctx)
        generated_types = set(qre.section_types())
        for st in matrix.required_sections():
            assert st.value in generated_types

    def test_deselected_optional_not_generated(self):
        draft = _draft(Methodology.SEGMENTATION)
        matrix = get_matrix(Methodology.SEGMENTATION)
        required_only = [st.value for st in matrix.required_sections()]
        draft.update_sections(required_only)
        ctx = _ctx(Methodology.SEGMENTATION)
        qre = generate_questionnaire(draft, ctx)
        optional_types = {st.value for st in matrix.optional_sections()}
        generated_types = set(qre.section_types())
        # No optional sections should be present
        assert generated_types.isdisjoint(optional_types)

    @pytest.mark.parametrize("methodology", list(Methodology))
    def test_generation_works_for_all_methodologies(self, methodology: Methodology):
        draft = _draft(methodology)
        ctx = AssistantContext(
            project_id="proj-001",
            stage=WorkflowStage.QUESTIONNAIRE,
            methodology=methodology,
            brief=_brief(),
            selected_sections=[st.value for st in get_matrix(methodology).section_order],
        )
        qre = generate_questionnaire(draft, ctx)
        assert len(qre.sections) >= 3
        assert qre.methodology == methodology.value


# ---------------------------------------------------------------------------
# AC-3: Structure conforms to schema and section order
# ---------------------------------------------------------------------------

class TestSchemaConformance:
    def test_questionnaire_has_required_fields(self):
        draft = _draft()
        ctx = _ctx()
        qre = generate_questionnaire(draft, ctx)
        assert qre.questionnaire_id
        assert qre.project_id == "proj-001"
        assert qre.methodology == "segmentation"
        assert qre.version == 1
        assert qre.total_questions > 0
        assert qre.estimated_loi_minutes > 0
        assert qre.created_at is not None

    def test_section_order_matches_matrix(self):
        draft = _draft(Methodology.SEGMENTATION)
        ctx = _ctx(Methodology.SEGMENTATION)
        qre = generate_questionnaire(draft, ctx)
        matrix = get_matrix(Methodology.SEGMENTATION)
        expected_order = [st.value for st in matrix.section_order]
        actual_order = qre.section_types()
        # Actual should be a subsequence of expected (only selected ones)
        expected_iter = iter(expected_order)
        for actual_type in actual_order:
            for expected_type in expected_iter:
                if expected_type == actual_type:
                    break
            else:
                pytest.fail(f"Section {actual_type} out of matrix order")

    def test_each_section_has_required_fields(self):
        draft = _draft()
        ctx = _ctx()
        qre = generate_questionnaire(draft, ctx)
        for section in qre.sections:
            assert section.section_id
            assert section.section_type
            assert section.label
            assert section.order >= 0
            assert isinstance(section.questions, list)

    def test_each_question_has_required_fields(self):
        draft = _draft()
        ctx = _ctx()
        qre = generate_questionnaire(draft, ctx)
        for section in qre.sections:
            for q in section.questions:
                assert q.question_id
                assert q.question_text
                assert q.question_type
                assert q.var_name

    def test_screener_has_termination_rules(self):
        draft = _draft()
        ctx = _ctx()
        qre = generate_questionnaire(draft, ctx)
        screener = qre.get_section("screener")
        assert screener is not None
        has_terminate = False
        for q in screener.questions:
            for opt in q.response_options:
                if opt.terminates:
                    has_terminate = True
        assert has_terminate, "Screener must have at least one termination rule"

    def test_attitudes_use_uniform_likert_scale(self):
        draft = _draft()
        ctx = _ctx()
        qre = generate_questionnaire(draft, ctx)
        attitudes = qre.get_section("attitudes")
        assert attitudes is not None
        scales = {q.scale_points for q in attitudes.questions}
        assert len(scales) == 1, "All attitude items must use the same scale"

    def test_attitudes_have_minimum_items(self):
        draft = _draft()
        ctx = _ctx()
        qre = generate_questionnaire(draft, ctx)
        attitudes = qre.get_section("attitudes")
        assert attitudes is not None
        assert len(attitudes.questions) >= 15

    def test_section_orders_are_sequential(self):
        draft = _draft()
        ctx = _ctx()
        qre = generate_questionnaire(draft, ctx)
        orders = [s.order for s in qre.sections]
        assert orders == list(range(len(orders)))

    def test_question_ids_unique_across_questionnaire(self):
        draft = _draft()
        ctx = _ctx()
        qre = generate_questionnaire(draft, ctx)
        all_ids = [q.question_id for s in qre.sections for q in s.questions]
        assert len(all_ids) == len(set(all_ids))

    def test_total_questions_computed(self):
        draft = _draft()
        ctx = _ctx()
        qre = generate_questionnaire(draft, ctx)
        manual_count = sum(len(s.questions) for s in qre.sections)
        assert qre.total_questions == manual_count

    def test_brief_content_grounded_in_questions(self):
        """Questions should reference brief content (category)."""
        draft = _draft()
        ctx = _ctx()
        qre = generate_questionnaire(draft, ctx)
        all_text = " ".join(q.question_text for s in qre.sections for q in s.questions)
        assert "snack bar" in all_text.lower()
