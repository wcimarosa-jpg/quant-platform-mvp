"""Contract tests for section-level edit/regenerate (P03-03).

AC-1: Users can regenerate one section without replacing others.
AC-2: Assistant explains what changed and why.
AC-3: Changes are versioned with diff metadata.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from packages.shared.assistant_context import (
    AssistantContext,
    BriefContext,
    Methodology,
    WorkflowStage,
)
from packages.shared.draft_config import DraftStore
from packages.shared.questionnaire_schema import Question, QuestionType, Section
from packages.survey_generation.engine import generate_questionnaire
from packages.survey_generation.section_editor import (
    ChangeHistory,
    EditResult,
    SectionChange,
    SectionDiff,
    compute_section_diff,
    regenerate_section,
)

NOW = datetime.now(tz=timezone.utc)


def _ctx() -> AssistantContext:
    return AssistantContext(
        project_id="proj-001",
        stage=WorkflowStage.QUESTIONNAIRE,
        methodology=Methodology.SEGMENTATION,
        brief=BriefContext(
            brief_id="brief-001",
            objectives="Understand brand health for KIND Bars",
            audience="US adults 18-54",
            category="premium snack bars",
            geography="United States",
            uploaded_at=NOW,
        ),
        selected_sections=["screener", "attitudes", "demographics"],
    )


def _generate():
    store = DraftStore()
    draft = store.create("proj-001", Methodology.SEGMENTATION)
    ctx = _ctx()
    return generate_questionnaire(draft, ctx), ctx


# ---------------------------------------------------------------------------
# AC-1: Regenerate one section without replacing others
# ---------------------------------------------------------------------------

class TestIsolatedRegeneration:
    def test_regenerate_only_changes_target_section(self):
        qre, ctx = _generate()
        # Snapshot other sections
        other_sections_before = {
            s.section_type: [q.question_id for q in s.questions]
            for s in qre.sections if s.section_type != "screener"
        }

        result = regenerate_section(qre, "screener", "Add more screening questions", ctx)

        other_sections_after = {
            s.section_type: [q.question_id for q in s.questions]
            for s in qre.sections if s.section_type != "screener"
        }
        assert other_sections_before == other_sections_after

    def test_untouched_sections_listed_in_result(self):
        qre, ctx = _generate()
        result = regenerate_section(qre, "attitudes", "Make statements more specific", ctx)
        assert "screener" in result.sections_untouched
        assert "demographics" in result.sections_untouched
        assert "attitudes" not in result.sections_untouched

    def test_regenerate_preserves_section_count(self):
        qre, ctx = _generate()
        count_before = len(qre.sections)
        regenerate_section(qre, "screener", "Simplify screener", ctx)
        assert len(qre.sections) == count_before

    def test_regenerate_preserves_section_order(self):
        qre, ctx = _generate()
        order_before = [s.section_type for s in qre.sections]
        regenerate_section(qre, "attitudes", "Add more items", ctx)
        order_after = [s.section_type for s in qre.sections]
        assert order_before == order_after

    def test_regenerate_nonexistent_section_raises(self):
        qre, ctx = _generate()
        with pytest.raises(ValueError, match="not found"):
            regenerate_section(qre, "nonexistent_section", "test", ctx)

    def test_multiple_regenerations_independent(self):
        qre, ctx = _generate()
        r1 = regenerate_section(qre, "screener", "First edit", ctx)
        r2 = regenerate_section(qre, "attitudes", "Second edit", ctx)
        # Both should have their own change records
        assert r1.section_type == "screener"
        assert r2.section_type == "attitudes"
        assert r1.change.change_id != r2.change.change_id


# ---------------------------------------------------------------------------
# AC-2: Assistant explains what changed and why
# ---------------------------------------------------------------------------

class TestChangeExplanation:
    def test_explanation_references_user_instruction(self):
        qre, ctx = _generate()
        result = regenerate_section(qre, "screener", "Add age verification question", ctx)
        assert "Add age verification question" in result.change.explanation

    def test_explanation_references_section_type(self):
        qre, ctx = _generate()
        result = regenerate_section(qre, "screener", "Simplify", ctx)
        assert "screener" in result.change.explanation

    def test_explanation_mentions_changes(self):
        qre, ctx = _generate()
        result = regenerate_section(qre, "screener", "Rewrite questions", ctx)
        explanation = result.change.explanation.lower()
        # Should mention at least one type of change
        has_change_info = (
            "added" in explanation
            or "removed" in explanation
            or "modified" in explanation
            or "unchanged" in explanation
        )
        assert has_change_info

    def test_change_record_has_user_instruction(self):
        qre, ctx = _generate()
        result = regenerate_section(qre, "screener", "Make it shorter", ctx)
        assert result.change.user_instruction == "Make it shorter"
        assert result.change.action == "regenerate"

    def test_change_has_timestamp(self):
        qre, ctx = _generate()
        result = regenerate_section(qre, "screener", "test", ctx)
        assert result.change.timestamp is not None


# ---------------------------------------------------------------------------
# AC-3: Changes are versioned with diff metadata
# ---------------------------------------------------------------------------

class TestVersioningAndDiff:
    def test_version_increments_on_regenerate(self):
        qre, ctx = _generate()
        assert qre.version == 1
        regenerate_section(qre, "screener", "edit 1", ctx)
        assert qre.version == 2
        regenerate_section(qre, "attitudes", "edit 2", ctx)
        assert qre.version == 3

    def test_result_contains_new_version(self):
        qre, ctx = _generate()
        result = regenerate_section(qre, "screener", "test", ctx)
        assert result.new_version == 2

    def test_diff_has_required_fields(self):
        qre, ctx = _generate()
        result = regenerate_section(qre, "screener", "test", ctx)
        diff = result.diff
        assert diff.section_type == "screener"
        assert diff.before_question_count >= 0
        assert diff.after_question_count >= 0
        assert isinstance(diff.added, list)
        assert isinstance(diff.removed, list)
        assert isinstance(diff.modified, list)
        assert isinstance(diff.unchanged, list)

    def test_diff_counts_are_consistent(self):
        qre, ctx = _generate()
        result = regenerate_section(qre, "screener", "test", ctx)
        diff = result.diff
        # Total after should match added + modified + unchanged
        assert diff.after_question_count == len(diff.added) + len(diff.modified) + len(diff.unchanged)

    def test_change_lists_question_ids(self):
        qre, ctx = _generate()
        result = regenerate_section(qre, "screener", "test", ctx)
        change = result.change
        assert isinstance(change.questions_added, list)
        assert isinstance(change.questions_removed, list)
        assert isinstance(change.questions_modified, list)


# ---------------------------------------------------------------------------
# Diff computation unit tests
# ---------------------------------------------------------------------------

class TestComputeDiff:
    def test_diff_new_section(self):
        section = Section(
            section_id="test", section_type="test", label="Test", order=0,
            questions=[
                Question(question_id="Q1", question_text="Q1?", question_type=QuestionType.OPEN_ENDED, var_name="Q1"),
            ],
        )
        diff = compute_section_diff(None, section)
        assert diff.added == ["Q1"]
        assert diff.removed == []
        assert diff.before_question_count == 0
        assert diff.after_question_count == 1

    def test_diff_identical_sections(self):
        section = Section(
            section_id="test", section_type="test", label="Test", order=0,
            questions=[
                Question(question_id="Q1", question_text="Same text", question_type=QuestionType.OPEN_ENDED, var_name="Q1"),
            ],
        )
        diff = compute_section_diff(section, section)
        assert diff.added == []
        assert diff.removed == []
        assert diff.modified == []
        assert diff.unchanged == ["Q1"]

    def test_diff_modified_question(self):
        before = Section(
            section_id="test", section_type="test", label="Test", order=0,
            questions=[
                Question(question_id="Q1", question_text="Old text", question_type=QuestionType.OPEN_ENDED, var_name="Q1"),
            ],
        )
        after = Section(
            section_id="test", section_type="test", label="Test", order=0,
            questions=[
                Question(question_id="Q1", question_text="New text", question_type=QuestionType.OPEN_ENDED, var_name="Q1"),
            ],
        )
        diff = compute_section_diff(before, after)
        assert diff.modified == ["Q1"]
        assert diff.unchanged == []

    def test_diff_added_and_removed(self):
        before = Section(
            section_id="test", section_type="test", label="Test", order=0,
            questions=[
                Question(question_id="Q1", question_text="Q1", question_type=QuestionType.OPEN_ENDED, var_name="Q1"),
            ],
        )
        after = Section(
            section_id="test", section_type="test", label="Test", order=0,
            questions=[
                Question(question_id="Q2", question_text="Q2", question_type=QuestionType.OPEN_ENDED, var_name="Q2"),
            ],
        )
        diff = compute_section_diff(before, after)
        assert diff.added == ["Q2"]
        assert diff.removed == ["Q1"]


# ---------------------------------------------------------------------------
# Change history
# ---------------------------------------------------------------------------

class TestChangeHistory:
    def test_record_and_retrieve(self):
        history = ChangeHistory()
        qre, ctx = _generate()
        result = regenerate_section(qre, "screener", "test", ctx)
        history.record(qre.questionnaire_id, result.change)
        records = history.get_history(qre.questionnaire_id)
        assert len(records) == 1
        assert records[0].section_type == "screener"

    def test_multiple_changes_tracked(self):
        history = ChangeHistory()
        qre, ctx = _generate()
        r1 = regenerate_section(qre, "screener", "edit 1", ctx)
        r2 = regenerate_section(qre, "attitudes", "edit 2", ctx)
        history.record(qre.questionnaire_id, r1.change)
        history.record(qre.questionnaire_id, r2.change)
        assert len(history.get_history(qre.questionnaire_id)) == 2

    def test_filter_by_section(self):
        history = ChangeHistory()
        qre, ctx = _generate()
        r1 = regenerate_section(qre, "screener", "edit 1", ctx)
        r2 = regenerate_section(qre, "attitudes", "edit 2", ctx)
        history.record(qre.questionnaire_id, r1.change)
        history.record(qre.questionnaire_id, r2.change)
        screener_changes = history.get_by_section(qre.questionnaire_id, "screener")
        assert len(screener_changes) == 1

    def test_empty_history(self):
        history = ChangeHistory()
        assert history.get_history("nonexistent") == []
