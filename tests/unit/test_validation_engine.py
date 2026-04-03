"""Contract tests for questionnaire validation engine (P04-01).

AC-1: Validation reports include section/question references.
AC-2: Blocking issues prevent publish/export.
AC-3: Validation aligns with analysis prerequisites.
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
from packages.shared.questionnaire_schema import (
    Question,
    QuestionType,
    Questionnaire,
    ResponseOption,
    Section,
)
from packages.shared.validation_engine import (
    ALL_CHECKS,
    IssueSeverity,
    ValidationReport,
    check_attitudes_minimum_items,
    check_likert_uniform_scale,
    check_maxdiff_minimum_tasks,
    check_questions_have_var_names,
    check_response_codes_exhaustive,
    check_satisfaction_dv_present,
    check_screener_has_termination,
    check_unique_question_ids,
    validate_questionnaire,
)
from packages.survey_generation.engine import generate_questionnaire

NOW = datetime.now(tz=timezone.utc)


def _generate_valid() -> Questionnaire:
    store = DraftStore()
    draft = store.create("proj-001", Methodology.SEGMENTATION)
    ctx = AssistantContext(
        project_id="proj-001",
        stage=WorkflowStage.QUESTIONNAIRE,
        methodology=Methodology.SEGMENTATION,
        brief=BriefContext(
            brief_id="brief-001",
            objectives="Test",
            audience="Adults",
            category="snack bars",
            geography="US",
            uploaded_at=NOW,
        ),
        selected_sections=["screener", "attitudes", "demographics"],
    )
    return generate_questionnaire(draft, ctx)


def _minimal_qre(**kwargs) -> Questionnaire:
    defaults = dict(project_id="proj-001", methodology="segmentation", sections=[])
    defaults.update(kwargs)
    return Questionnaire(**defaults)


# ---------------------------------------------------------------------------
# AC-1: Reports include section/question references
# ---------------------------------------------------------------------------

class TestReportReferences:
    def test_issue_has_section_reference(self):
        qre = _minimal_qre(sections=[
            Section(section_id="s1", section_type="screener", label="Screener", order=0,
                    questions=[
                        Question(question_id="Q1", question_text="Q?",
                                 question_type=QuestionType.SINGLE_SELECT, var_name="Q1",
                                 response_options=[ResponseOption(code=1, label="Yes")]),
                    ]),
        ])
        report = validate_questionnaire(qre)
        code_issues = [i for i in report.issues if i.check_name == "response_codes_exhaustive"]
        assert len(code_issues) >= 1
        assert code_issues[0].section_type == "screener"

    def test_issue_has_question_reference(self):
        qre = _minimal_qre(sections=[
            Section(section_id="s1", section_type="screener", label="S", order=0,
                    questions=[
                        Question(question_id="Q1", question_text="Q?",
                                 question_type=QuestionType.SINGLE_SELECT, var_name="Q1",
                                 response_options=[ResponseOption(code=1, label="Only one")]),
                    ]),
        ])
        report = validate_questionnaire(qre)
        code_issues = [i for i in report.issues if i.check_name == "response_codes_exhaustive"]
        assert code_issues[0].question_id == "Q1"

    def test_issue_has_suggestion(self):
        qre = _minimal_qre(sections=[
            Section(section_id="s1", section_type="screener", label="S", order=0,
                    questions=[
                        Question(question_id="Q1", question_text="Q?",
                                 question_type=QuestionType.SINGLE_SELECT, var_name="Q1",
                                 response_options=[ResponseOption(code=1, label="Only")]),
                    ]),
        ])
        report = validate_questionnaire(qre)
        assert any(i.suggestion is not None for i in report.issues)

    def test_for_ui_output(self):
        qre = _generate_valid()
        report = validate_questionnaire(qre)
        ui = report.for_ui()
        assert isinstance(ui, list)
        for item in ui:
            assert "issue_id" in item
            assert "severity" in item
            assert "check_name" in item
            assert "message" in item

    def test_issue_ids_are_unique(self):
        qre = _generate_valid()
        report = validate_questionnaire(qre)
        ids = [i.issue_id for i in report.issues]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# AC-2: Blocking issues prevent publish/export
# ---------------------------------------------------------------------------

class TestPublishGating:
    def test_valid_questionnaire_can_publish(self):
        qre = _generate_valid()
        report = validate_questionnaire(qre)
        assert report.can_publish is True

    def test_missing_response_codes_blocks_publish(self):
        qre = _minimal_qre(sections=[
            Section(section_id="s1", section_type="test", label="T", order=0,
                    questions=[
                        Question(question_id="Q1", question_text="Q?",
                                 question_type=QuestionType.SINGLE_SELECT, var_name="Q1",
                                 response_options=[ResponseOption(code=1, label="Only")]),
                    ]),
        ])
        report = validate_questionnaire(qre)
        assert report.can_publish is False
        assert report.error_count >= 1

    def test_duplicate_question_ids_blocks_publish(self):
        q = Question(question_id="DUP", question_text="Q?", question_type=QuestionType.OPEN_ENDED, var_name="DUP")
        qre = _minimal_qre(sections=[
            Section(section_id="s1", section_type="a", label="A", order=0, questions=[q]),
            Section(section_id="s2", section_type="b", label="B", order=1, questions=[
                Question(question_id="DUP", question_text="Q2?", question_type=QuestionType.OPEN_ENDED, var_name="DUP2"),
            ]),
        ])
        report = validate_questionnaire(qre)
        assert report.can_publish is False
        dup_issues = [i for i in report.issues if i.check_name == "unique_question_ids"]
        assert len(dup_issues) >= 1

    def test_warnings_do_not_block_publish(self):
        qre = _generate_valid()
        report = validate_questionnaire(qre)
        # Even if warnings exist, can_publish should be True if no errors
        if report.warning_count > 0:
            assert report.can_publish is True

    def test_error_vs_warning_counts(self):
        qre = _generate_valid()
        report = validate_questionnaire(qre)
        assert report.error_count + report.warning_count == len(report.issues)


# ---------------------------------------------------------------------------
# AC-3: Validation aligns with analysis prerequisites
# ---------------------------------------------------------------------------

class TestAnalysisAlignment:
    def test_attitudes_minimum_for_clustering(self):
        """K-Means requires 15+ attitude items."""
        qre = _minimal_qre(sections=[
            Section(section_id="att", section_type="attitudes", label="Attitudes", order=0,
                    questions=[
                        Question(question_id=f"A{i}", question_text=f"Stmt {i}",
                                 question_type=QuestionType.LIKERT_SCALE, var_name=f"A{i}",
                                 scale_points=5)
                        for i in range(10)  # only 10, need 15
                    ]),
        ])
        issues = check_attitudes_minimum_items(qre)
        assert len(issues) >= 1
        assert issues[0].severity == IssueSeverity.ERROR
        assert "15" in issues[0].message

    def test_attitudes_15_items_passes(self):
        qre = _minimal_qre(sections=[
            Section(section_id="att", section_type="attitudes", label="Attitudes", order=0,
                    questions=[
                        Question(question_id=f"A{i}", question_text=f"Stmt {i}",
                                 question_type=QuestionType.LIKERT_SCALE, var_name=f"A{i}",
                                 scale_points=5)
                        for i in range(15)
                    ]),
        ])
        issues = check_attitudes_minimum_items(qre)
        assert len(issues) == 0

    def test_mixed_likert_scales_blocked(self):
        """All Likert items in a section must use the same scale."""
        qre = _minimal_qre(sections=[
            Section(section_id="att", section_type="attitudes", label="Attitudes", order=0,
                    questions=[
                        Question(question_id="A1", question_text="5pt", question_type=QuestionType.LIKERT_SCALE, var_name="A1", scale_points=5),
                        Question(question_id="A2", question_text="7pt", question_type=QuestionType.LIKERT_SCALE, var_name="A2", scale_points=7),
                    ]),
        ])
        issues = check_likert_uniform_scale(qre)
        assert len(issues) >= 1
        assert issues[0].severity == IssueSeverity.ERROR

    def test_uniform_likert_passes(self):
        qre = _minimal_qre(sections=[
            Section(section_id="att", section_type="attitudes", label="Attitudes", order=0,
                    questions=[
                        Question(question_id="A1", question_text="S1", question_type=QuestionType.LIKERT_SCALE, var_name="A1", scale_points=5),
                        Question(question_id="A2", question_text="S2", question_type=QuestionType.LIKERT_SCALE, var_name="A2", scale_points=5),
                    ]),
        ])
        issues = check_likert_uniform_scale(qre)
        assert len(issues) == 0

    def test_maxdiff_minimum_tasks(self):
        """MaxDiff HB estimation requires 12+ tasks."""
        qre = _minimal_qre(sections=[
            Section(section_id="md", section_type="maxdiff_exercise", label="MaxDiff", order=0,
                    questions=[
                        Question(question_id=f"MD{i}", question_text=f"Task {i}",
                                 question_type=QuestionType.MAXDIFF_TASK, var_name=f"MD{i}")
                        for i in range(8)  # only 8, need 12
                    ]),
        ])
        issues = check_maxdiff_minimum_tasks(qre)
        assert len(issues) >= 1
        assert "12" in issues[0].message

    def test_satisfaction_dv_warning(self):
        """Regression needs numeric DVs in satisfaction section."""
        qre = _minimal_qre(sections=[
            Section(section_id="sat", section_type="satisfaction_outcomes", label="Satisfaction", order=0,
                    questions=[
                        Question(question_id="S1", question_text="Open end",
                                 question_type=QuestionType.OPEN_ENDED, var_name="S1"),
                    ]),
        ])
        issues = check_satisfaction_dv_present(qre)
        assert len(issues) >= 1
        assert issues[0].severity == IssueSeverity.WARNING

    def test_screener_termination_required(self):
        qre = _minimal_qre(sections=[
            Section(section_id="scr", section_type="screener", label="Screener", order=0,
                    questions=[
                        Question(question_id="S1", question_text="Q?",
                                 question_type=QuestionType.SINGLE_SELECT, var_name="S1",
                                 response_options=[
                                     ResponseOption(code=1, label="Yes"),
                                     ResponseOption(code=2, label="No"),  # no terminates flag
                                 ]),
                    ]),
        ])
        issues = check_screener_has_termination(qre)
        assert len(issues) >= 1


# ---------------------------------------------------------------------------
# Full validation run
# ---------------------------------------------------------------------------

class TestFullValidation:
    def test_generated_questionnaire_passes_validation(self):
        qre = _generate_valid()
        report = validate_questionnaire(qre)
        assert report.can_publish is True
        assert report.checks_run == len(ALL_CHECKS)

    def test_report_has_methodology(self):
        qre = _generate_valid()
        report = validate_questionnaire(qre)
        assert report.methodology == "segmentation"

    def test_empty_questionnaire_has_no_errors(self):
        """Empty questionnaire has no sections to validate."""
        qre = _minimal_qre()
        report = validate_questionnaire(qre)
        assert report.error_count == 0  # no sections = nothing to fail

    def test_var_names_required(self):
        qre = _minimal_qre(sections=[
            Section(section_id="s1", section_type="test", label="T", order=0,
                    questions=[
                        Question(question_id="Q1", question_text="Q?",
                                 question_type=QuestionType.OPEN_ENDED, var_name=""),
                    ]),
        ])
        report = validate_questionnaire(qre)
        var_issues = [i for i in report.issues if i.check_name == "question_var_name"]
        assert len(var_issues) >= 1
