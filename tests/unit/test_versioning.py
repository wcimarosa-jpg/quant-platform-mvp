"""Contract tests for questionnaire versioning and compare (P03-04).

AC-1: Versions v1..vn are persisted.
AC-2: Compare view shows section-level additions/removals/edits.
AC-3: Users can revert or fork from prior version.
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
from packages.shared.questionnaire_schema import Question, QuestionType, Questionnaire, Section
from packages.survey_generation.engine import generate_questionnaire
from packages.survey_generation.section_editor import regenerate_section
from packages.survey_generation.versioning import (
    VersionComparison,
    VersionEntry,
    VersionStore,
    compare_versions,
)

NOW = datetime.now(tz=timezone.utc)


def _ctx() -> AssistantContext:
    return AssistantContext(
        project_id="proj-001",
        stage=WorkflowStage.QUESTIONNAIRE,
        methodology=Methodology.SEGMENTATION,
        brief=BriefContext(
            brief_id="brief-001",
            objectives="Understand brand health",
            audience="US adults 18-54",
            category="premium snack bars",
            geography="United States",
            uploaded_at=NOW,
        ),
        selected_sections=["screener", "attitudes", "demographics"],
    )


def _generate() -> Questionnaire:
    store = DraftStore()
    draft = store.create("proj-001", Methodology.SEGMENTATION)
    return generate_questionnaire(draft, _ctx())


# ---------------------------------------------------------------------------
# AC-1: Versions v1..vn are persisted
# ---------------------------------------------------------------------------

class TestVersionPersistence:
    def test_save_and_retrieve_v1(self):
        vs = VersionStore()
        qre = _generate()
        entry = vs.save_version(qre, "user", "Initial generation")
        assert entry.version == 1
        assert entry.author == "user"
        retrieved = vs.get_version(qre.questionnaire_id, 1)
        assert retrieved is not None
        assert retrieved.version == 1

    def test_save_multiple_versions(self):
        vs = VersionStore()
        qre = _generate()
        vs.save_version(qre, "user", "v1")
        qre.version = 2
        vs.save_version(qre, "assistant", "v2 after edit")
        qre.version = 3
        vs.save_version(qre, "user", "v3 final")

        assert vs.get_version(qre.questionnaire_id, 1) is not None
        assert vs.get_version(qre.questionnaire_id, 2) is not None
        assert vs.get_version(qre.questionnaire_id, 3) is not None

    def test_get_latest(self):
        vs = VersionStore()
        qre = _generate()
        vs.save_version(qre, "user", "v1")
        qre.version = 2
        vs.save_version(qre, "user", "v2")
        latest = vs.get_latest(qre.questionnaire_id)
        assert latest is not None
        assert latest.version == 2

    def test_list_versions(self):
        vs = VersionStore()
        qre = _generate()
        vs.save_version(qre, "user", "Initial")
        qre.version = 2
        vs.save_version(qre, "assistant", "Regenerated screener")
        summaries = vs.list_versions(qre.questionnaire_id)
        assert len(summaries) == 2
        assert summaries[0]["version"] == 1
        assert summaries[1]["version"] == 2
        for s in summaries:
            assert "author" in s
            assert "message" in s
            assert "created_at" in s
            assert "section_count" in s
            assert "question_count" in s

    def test_versions_are_snapshots(self):
        """Modifying the questionnaire after save should not affect stored version."""
        vs = VersionStore()
        qre = _generate()
        vs.save_version(qre, "user", "v1")
        original_count = qre.total_questions
        # Mutate the live questionnaire
        qre.sections[0].questions.clear()
        qre.total_questions = 0
        # Stored version should be unaffected
        stored = vs.get_version(qre.questionnaire_id, 1)
        assert stored.questionnaire.total_questions == original_count

    def test_get_nonexistent_version_returns_none(self):
        vs = VersionStore()
        assert vs.get_version("nonexistent", 1) is None

    def test_get_latest_empty_returns_none(self):
        vs = VersionStore()
        assert vs.get_latest("nonexistent") is None

    def test_count(self):
        vs = VersionStore()
        assert vs.count == 0
        qre = _generate()
        vs.save_version(qre, "user", "v1")
        assert vs.count == 1


# ---------------------------------------------------------------------------
# AC-2: Compare view shows section-level additions/removals/edits
# ---------------------------------------------------------------------------

class TestCompareView:
    def test_compare_identical_versions(self):
        vs = VersionStore()
        qre = _generate()
        vs.save_version(qre, "user", "v1")
        qre.version = 2
        vs.save_version(qre, "user", "v2 no changes")
        result = vs.compare(qre.questionnaire_id, 1, 2)
        assert len(result.sections_added) == 0
        assert len(result.sections_removed) == 0
        assert len(result.sections_changed) == 0
        assert len(result.sections_unchanged) >= 3

    def test_compare_after_section_regeneration(self):
        from packages.shared.questionnaire_schema import Question, QuestionType, Section
        vs = VersionStore()
        qre = _generate()
        ctx = _ctx()
        vs.save_version(qre, "user", "v1")

        # Use custom generator that produces different questions
        def _custom_gen(ctx, order):
            return Section(
                section_id="screener", section_type="screener", label="Screener", order=order,
                questions=[
                    Question(question_id="SCR_NEW_01", question_text="New question?",
                             question_type=QuestionType.OPEN_ENDED, var_name="SCR_NEW_01"),
                ],
            )
        regenerate_section(qre, "screener", "Simplify", ctx, generator_fn=_custom_gen)
        vs.save_version(qre, "user", "v2 regenerated screener")
        result = vs.compare(qre.questionnaire_id, 1, 2)
        changed_types = {d.section_type for d in result.sections_changed}
        assert "screener" in changed_types
        # Other sections should be unchanged
        assert len(result.sections_unchanged) >= 2

    def test_compare_detects_section_addition(self):
        qre1 = Questionnaire(
            project_id="proj-001", methodology="segmentation", version=1,
            sections=[
                Section(section_id="s1", section_type="screener", label="Screener", order=0, questions=[]),
            ],
        )
        qre2 = Questionnaire(
            project_id="proj-001", methodology="segmentation", version=2,
            sections=[
                Section(section_id="s1", section_type="screener", label="Screener", order=0, questions=[]),
                Section(section_id="s2", section_type="demographics", label="Demographics", order=1, questions=[]),
            ],
        )
        result = compare_versions(qre1, qre2)
        assert "demographics" in result.sections_added
        assert len(result.sections_removed) == 0

    def test_compare_detects_section_removal(self):
        qre1 = Questionnaire(
            project_id="proj-001", methodology="segmentation", version=1,
            sections=[
                Section(section_id="s1", section_type="screener", label="Screener", order=0, questions=[]),
                Section(section_id="s2", section_type="demographics", label="Demographics", order=1, questions=[]),
            ],
        )
        qre2 = Questionnaire(
            project_id="proj-001", methodology="segmentation", version=2,
            sections=[
                Section(section_id="s1", section_type="screener", label="Screener", order=0, questions=[]),
            ],
        )
        result = compare_versions(qre1, qre2)
        assert "demographics" in result.sections_removed

    def test_compare_shows_question_level_diffs(self):
        q1 = Question(question_id="Q1", question_text="Old text", question_type=QuestionType.OPEN_ENDED, var_name="Q1")
        q1_mod = Question(question_id="Q1", question_text="New text", question_type=QuestionType.OPEN_ENDED, var_name="Q1")
        qre1 = Questionnaire(
            project_id="proj-001", methodology="segmentation", version=1,
            sections=[Section(section_id="s1", section_type="screener", label="S", order=0, questions=[q1])],
        )
        qre2 = Questionnaire(
            project_id="proj-001", methodology="segmentation", version=2,
            sections=[Section(section_id="s1", section_type="screener", label="S", order=0, questions=[q1_mod])],
        )
        result = compare_versions(qre1, qre2)
        assert len(result.sections_changed) == 1
        assert "Q1" in result.sections_changed[0].modified

    def test_compare_result_has_version_numbers(self):
        vs = VersionStore()
        qre = _generate()
        vs.save_version(qre, "user", "v1")
        qre.version = 2
        vs.save_version(qre, "user", "v2")
        result = vs.compare(qre.questionnaire_id, 1, 2)
        assert result.base_version == 1
        assert result.compare_version == 2

    def test_compare_nonexistent_version_raises(self):
        vs = VersionStore()
        qre = _generate()
        vs.save_version(qre, "user", "v1")
        with pytest.raises(ValueError, match="not found"):
            vs.compare(qre.questionnaire_id, 1, 99)


# ---------------------------------------------------------------------------
# AC-3: Revert or fork from prior version
# ---------------------------------------------------------------------------

class TestRevertAndFork:
    def test_revert_creates_new_version(self):
        vs = VersionStore()
        qre = _generate()
        vs.save_version(qre, "user", "v1")
        regenerate_section(qre, "screener", "Change", _ctx())
        vs.save_version(qre, "user", "v2")
        reverted = vs.revert(qre.questionnaire_id, 1)
        assert reverted.version == 3  # new version, not overwrite
        latest = vs.get_latest(qre.questionnaire_id)
        assert latest.version == 3
        assert latest.parent_version == 1
        assert "Reverted" in latest.message

    def test_revert_restores_content(self):
        vs = VersionStore()
        qre = _generate()
        v1_sections = [s.section_type for s in qre.sections]
        v1_q_count = qre.total_questions
        vs.save_version(qre, "user", "v1")
        regenerate_section(qre, "screener", "Change", _ctx())
        vs.save_version(qre, "user", "v2")
        reverted = vs.revert(qre.questionnaire_id, 1)
        assert [s.section_type for s in reverted.sections] == v1_sections
        assert reverted.total_questions == v1_q_count

    def test_revert_nonexistent_raises(self):
        vs = VersionStore()
        with pytest.raises(ValueError, match="not found"):
            vs.revert("nonexistent", 1)

    def test_fork_creates_new_questionnaire(self):
        vs = VersionStore()
        qre = _generate()
        vs.save_version(qre, "user", "v1")
        forked = vs.fork(qre.questionnaire_id, 1)
        assert forked.questionnaire_id != qre.questionnaire_id
        assert forked.version == 1
        assert forked.project_id == qre.project_id

    def test_fork_to_different_project(self):
        vs = VersionStore()
        qre = _generate()
        vs.save_version(qre, "user", "v1")
        forked = vs.fork(qre.questionnaire_id, 1, new_project_id="proj-002")
        assert forked.project_id == "proj-002"
        assert forked.questionnaire_id != qre.questionnaire_id

    def test_fork_preserves_sections(self):
        vs = VersionStore()
        qre = _generate()
        vs.save_version(qre, "user", "v1")
        forked = vs.fork(qre.questionnaire_id, 1)
        assert len(forked.sections) == len(qre.sections)
        assert forked.section_types() == qre.section_types()

    def test_fork_is_independent_copy(self):
        """Modifying forked questionnaire should not affect original."""
        vs = VersionStore()
        qre = _generate()
        vs.save_version(qre, "user", "v1")
        forked = vs.fork(qre.questionnaire_id, 1)
        forked.sections.clear()
        original = vs.get_version(qre.questionnaire_id, 1)
        assert len(original.questionnaire.sections) > 0

    def test_fork_nonexistent_raises(self):
        vs = VersionStore()
        with pytest.raises(ValueError, match="not found"):
            vs.fork("nonexistent", 1)
