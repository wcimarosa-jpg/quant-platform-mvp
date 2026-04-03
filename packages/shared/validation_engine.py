"""Questionnaire validation engine.

Runs structural, methodology, and analysis-compatibility checks
against a questionnaire. Reports include section/question references.
Blocking issues prevent publish/export.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .assistant_context import Methodology
from .questionnaire_schema import Questionnaire, QuestionType, Section
from .section_taxonomy import get_matrix


class IssueSeverity(str, Enum):
    ERROR = "error"      # Blocks publish/export
    WARNING = "warning"  # Allowed but flagged


class ValidationIssue(BaseModel):
    """One validation finding with section/question reference."""

    issue_id: str
    severity: IssueSeverity
    check_name: str
    section_type: str | None = None
    question_id: str | None = None
    message: str
    suggestion: str | None = None


class ValidationReport(BaseModel):
    """Complete validation report for a questionnaire."""

    questionnaire_id: str
    version: int
    methodology: str
    issues: list[ValidationIssue] = Field(default_factory=list)
    checks_run: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.WARNING)

    @property
    def can_publish(self) -> bool:
        return self.error_count == 0

    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.ERROR]

    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.WARNING]

    def for_ui(self) -> list[dict[str, Any]]:
        return [
            {
                "issue_id": i.issue_id,
                "severity": i.severity.value,
                "check_name": i.check_name,
                "section_type": i.section_type,
                "question_id": i.question_id,
                "message": i.message,
                "suggestion": i.suggestion,
            }
            for i in self.issues
        ]


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

class _IssueCounter:
    """Thread-local issue counter for deterministic IDs within a single validation run."""

    def __init__(self) -> None:
        self._n = 0

    def next_id(self) -> str:
        self._n += 1
        return f"VAL-{self._n:04d}"


# Module-level default; replaced per validate_questionnaire call
_counter = _IssueCounter()


def _issue(
    severity: IssueSeverity,
    check_name: str,
    message: str,
    section_type: str | None = None,
    question_id: str | None = None,
    suggestion: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        issue_id=_counter.next_id(),
        severity=severity,
        check_name=check_name,
        section_type=section_type,
        question_id=question_id,
        message=message,
        suggestion=suggestion,
    )


def check_screener_has_termination(qre: Questionnaire) -> list[ValidationIssue]:
    """Screener must have at least one termination rule."""
    issues = []
    screener = qre.get_section("screener")
    if not screener:
        return issues
    has_term = any(
        opt.terminates
        for q in screener.questions
        for opt in q.response_options
    )
    if not has_term:
        issues.append(_issue(
            IssueSeverity.ERROR,
            "screener_termination",
            "Screener has no termination rules. At least one response option must terminate non-qualifying respondents.",
            section_type="screener",
            suggestion="Add terminates=True to at least one disqualifying response option.",
        ))
    return issues


def check_response_codes_exhaustive(qre: Questionnaire) -> list[ValidationIssue]:
    """Single-select and multi-select questions must have response options."""
    issues = []
    for section in qre.sections:
        for q in section.questions:
            if q.question_type in (QuestionType.SINGLE_SELECT, QuestionType.MULTI_SELECT):
                if len(q.response_options) < 2:
                    issues.append(_issue(
                        IssueSeverity.ERROR,
                        "response_codes_exhaustive",
                        f"Question {q.question_id} has fewer than 2 response options.",
                        section_type=section.section_type,
                        question_id=q.question_id,
                        suggestion="Add at least 2 response options with unique codes.",
                    ))
    return issues


def check_unique_question_ids(qre: Questionnaire) -> list[ValidationIssue]:
    """All question IDs must be unique across the questionnaire."""
    issues = []
    seen: dict[str, str] = {}
    for section in qre.sections:
        for q in section.questions:
            if q.question_id in seen:
                issues.append(_issue(
                    IssueSeverity.ERROR,
                    "unique_question_ids",
                    f"Duplicate question ID '{q.question_id}' in sections '{seen[q.question_id]}' and '{section.section_type}'.",
                    section_type=section.section_type,
                    question_id=q.question_id,
                    suggestion="Ensure every question has a unique ID.",
                ))
            else:
                seen[q.question_id] = section.section_type
    return issues


def check_likert_uniform_scale(qre: Questionnaire) -> list[ValidationIssue]:
    """All Likert items in a section must use the same scale."""
    issues = []
    for section in qre.sections:
        likert_scales = set()
        for q in section.questions:
            if q.question_type == QuestionType.LIKERT_SCALE:
                likert_scales.add(q.scale_points)
        if len(likert_scales) > 1:
            issues.append(_issue(
                IssueSeverity.ERROR,
                "likert_uniform_scale",
                f"Section '{section.section_type}' has mixed Likert scales: {likert_scales}. All items must use the same scale.",
                section_type=section.section_type,
                suggestion="Standardize all Likert items to the same scale (e.g., all 5-point or all 7-point).",
            ))
    return issues


def check_attitudes_minimum_items(qre: Questionnaire) -> list[ValidationIssue]:
    """Attitudinal battery must have at least 15 items for clustering."""
    issues = []
    attitudes = qre.get_section("attitudes")
    if not attitudes:
        return issues
    if len(attitudes.questions) < 15:
        issues.append(_issue(
            IssueSeverity.ERROR,
            "attitudes_minimum_items",
            f"Attitudinal battery has {len(attitudes.questions)} items. Minimum 15 required for K-Means clustering.",
            section_type="attitudes",
            suggestion="Add more attitudinal statements to reach at least 15 items.",
        ))
    return issues


def check_satisfaction_dv_present(qre: Questionnaire) -> list[ValidationIssue]:
    """Satisfaction/outcomes section should have numeric scale items for regression DV."""
    issues = []
    sat = qre.get_section("satisfaction_outcomes")
    if not sat:
        return issues
    numeric_items = [
        q for q in sat.questions
        if q.question_type in (QuestionType.LIKERT_SCALE, QuestionType.NUMERIC)
    ]
    if len(numeric_items) == 0:
        issues.append(_issue(
            IssueSeverity.WARNING,
            "satisfaction_dv_present",
            "Satisfaction section has no numeric-scale items. Ridge regression requires numeric DVs.",
            section_type="satisfaction_outcomes",
            suggestion="Add at least one Likert or numeric scale question as a dependent variable.",
        ))
    return issues


def check_section_order_matches_matrix(qre: Questionnaire) -> list[ValidationIssue]:
    """Section order should follow the methodology matrix."""
    issues = []
    try:
        methodology = Methodology(qre.methodology)
    except ValueError:
        return issues
    matrix = get_matrix(methodology)
    expected_order = [st.value for st in matrix.section_order]
    actual_order = [s.section_type for s in qre.sections]

    # Check each section appears in the expected order
    expected_positions = {st: i for i, st in enumerate(expected_order)}
    last_pos = -1
    for actual_type in actual_order:
        pos = expected_positions.get(actual_type)
        if pos is None:
            continue  # unknown section type, skip order check
        if pos < last_pos:
            issues.append(_issue(
                IssueSeverity.WARNING,
                "section_order",
                f"Section '{actual_type}' is out of the expected methodology order.",
                section_type=actual_type,
                suggestion="Reorder sections to match the methodology's standard flow.",
            ))
        else:
            last_pos = pos
    return issues


def check_maxdiff_minimum_tasks(qre: Questionnaire) -> list[ValidationIssue]:
    """MaxDiff exercise must have at least 12 tasks."""
    issues = []
    md = qre.get_section("maxdiff_exercise")
    if not md:
        return issues
    if len(md.questions) < 12:
        issues.append(_issue(
            IssueSeverity.ERROR,
            "maxdiff_minimum_tasks",
            f"MaxDiff exercise has {len(md.questions)} tasks. Minimum 12 required for HB estimation.",
            section_type="maxdiff_exercise",
            suggestion="Add more MaxDiff tasks to reach at least 12.",
        ))
    return issues


def check_questions_have_var_names(qre: Questionnaire) -> list[ValidationIssue]:
    """Every question must have a non-empty var_name for data mapping."""
    issues = []
    for section in qre.sections:
        for q in section.questions:
            if not q.var_name or not q.var_name.strip():
                issues.append(_issue(
                    IssueSeverity.ERROR,
                    "question_var_name",
                    f"Question {q.question_id} has no variable name.",
                    section_type=section.section_type,
                    question_id=q.question_id,
                    suggestion="Assign a unique variable name (e.g., SCR_01, ATT_01).",
                ))
    return issues


# ---------------------------------------------------------------------------
# Check registry
# ---------------------------------------------------------------------------

ALL_CHECKS = [
    check_screener_has_termination,
    check_response_codes_exhaustive,
    check_unique_question_ids,
    check_likert_uniform_scale,
    check_attitudes_minimum_items,
    check_satisfaction_dv_present,
    check_section_order_matches_matrix,
    check_maxdiff_minimum_tasks,
    check_questions_have_var_names,
]


# ---------------------------------------------------------------------------
# Main validation function
# ---------------------------------------------------------------------------

def validate_questionnaire(qre: Questionnaire) -> ValidationReport:
    """Run all validation checks against a questionnaire.

    Returns a ValidationReport with issues and publish/export eligibility.
    """
    global _counter
    _counter = _IssueCounter()  # fresh counter per validation run

    report = ValidationReport(
        questionnaire_id=qre.questionnaire_id,
        version=qre.version,
        methodology=qre.methodology,
    )

    for check_fn in ALL_CHECKS:
        issues = check_fn(qre)
        report.issues.extend(issues)
        report.checks_run += 1

    return report
