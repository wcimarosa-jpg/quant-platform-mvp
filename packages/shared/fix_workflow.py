"""Assistant fix workflow for validation issues.

Generates targeted fix proposals for each validation failure,
lets users accept/reject individually, applies accepted fixes,
and re-validates automatically.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, Field

from .questionnaire_schema import (
    Question,
    QuestionType,
    Questionnaire,
    ResponseOption,
    Section,
)
from .validation_engine import (
    IssueSeverity,
    ValidationIssue,
    ValidationReport,
    validate_questionnaire,
)


class FixStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    APPLIED = "applied"


class FixProposal(BaseModel):
    """One proposed fix mapped to a specific validation issue."""

    fix_id: str = Field(default_factory=lambda: f"fix-{uuid.uuid4().hex[:8]}")
    issue_id: str           # maps to ValidationIssue.issue_id
    check_name: str         # which check produced the issue
    section_type: str | None = None
    question_id: str | None = None
    description: str        # what this fix will do
    status: FixStatus = FixStatus.PENDING


class FixSession(BaseModel):
    """A fix session for one validation report."""

    session_id: str = Field(default_factory=lambda: f"fixsess-{uuid.uuid4().hex[:8]}")
    questionnaire_id: str
    version: int
    proposals: list[FixProposal]
    revalidation_report: ValidationReport | None = None

    def pending(self) -> list[FixProposal]:
        return [p for p in self.proposals if p.status == FixStatus.PENDING]

    def accepted(self) -> list[FixProposal]:
        return [p for p in self.proposals if p.status == FixStatus.ACCEPTED]

    def all_resolved(self) -> bool:
        return len(self.pending()) == 0


# ---------------------------------------------------------------------------
# Fix generators — one per check_name
# ---------------------------------------------------------------------------

def _fix_screener_termination(issue: ValidationIssue, qre: Questionnaire) -> FixProposal:
    return FixProposal(
        issue_id=issue.issue_id,
        check_name=issue.check_name,
        section_type=issue.section_type,
        description="Add terminates=True to the last response option in the first screener question.",
    )


def _fix_response_codes(issue: ValidationIssue, qre: Questionnaire) -> FixProposal:
    return FixProposal(
        issue_id=issue.issue_id,
        check_name=issue.check_name,
        section_type=issue.section_type,
        question_id=issue.question_id,
        description=f"Add a second response option to question {issue.question_id}.",
    )


def _fix_unique_ids(issue: ValidationIssue, qre: Questionnaire) -> FixProposal:
    return FixProposal(
        issue_id=issue.issue_id,
        check_name=issue.check_name,
        section_type=issue.section_type,
        question_id=issue.question_id,
        description=f"Rename duplicate question ID '{issue.question_id}' with a unique suffix.",
    )


def _fix_likert_scale(issue: ValidationIssue, qre: Questionnaire) -> FixProposal:
    return FixProposal(
        issue_id=issue.issue_id,
        check_name=issue.check_name,
        section_type=issue.section_type,
        description="Standardize all Likert items in this section to 5-point scale.",
    )


def _fix_attitudes_minimum(issue: ValidationIssue, qre: Questionnaire) -> FixProposal:
    section = qre.get_section("attitudes")
    current = len(section.questions) if section else 0
    needed = 15 - current
    return FixProposal(
        issue_id=issue.issue_id,
        check_name=issue.check_name,
        section_type=issue.section_type,
        description=f"Add {needed} more attitudinal statements to reach the 15-item minimum.",
    )


def _fix_maxdiff_tasks(issue: ValidationIssue, qre: Questionnaire) -> FixProposal:
    section = qre.get_section("maxdiff_exercise")
    current = len(section.questions) if section else 0
    needed = 12 - current
    return FixProposal(
        issue_id=issue.issue_id,
        check_name=issue.check_name,
        section_type=issue.section_type,
        description=f"Add {needed} more MaxDiff tasks to reach the 12-task minimum.",
    )


def _fix_var_name(issue: ValidationIssue, qre: Questionnaire) -> FixProposal:
    return FixProposal(
        issue_id=issue.issue_id,
        check_name=issue.check_name,
        section_type=issue.section_type,
        question_id=issue.question_id,
        description=f"Auto-assign variable name based on section and question position.",
    )


# NOTE: attitudes_minimum_items and maxdiff_minimum_tasks are excluded because
# their fixes require LLM-generated content (new attitude statements / MaxDiff tasks).
# They will be supported once the LLM generation integration is available.
_FIX_GENERATORS: dict[str, Callable[[ValidationIssue, Questionnaire], FixProposal]] = {
    "screener_termination": _fix_screener_termination,
    "response_codes_exhaustive": _fix_response_codes,
    "unique_question_ids": _fix_unique_ids,
    "likert_uniform_scale": _fix_likert_scale,
    "question_var_name": _fix_var_name,
}


# ---------------------------------------------------------------------------
# Fix application — mutates the questionnaire
# ---------------------------------------------------------------------------

def _apply_screener_termination(qre: Questionnaire) -> None:
    screener = qre.get_section("screener")
    if not screener or not screener.questions:
        return
    q = screener.questions[0]
    if q.response_options:
        q.response_options[-1].terminates = True


def _apply_response_codes(qre: Questionnaire, question_id: str) -> None:
    for section in qre.sections:
        for q in section.questions:
            if q.question_id == question_id and len(q.response_options) < 2:
                existing_codes = {o.code for o in q.response_options}
                new_code = max(existing_codes, default=0) + 1
                q.response_options.append(ResponseOption(code=new_code, label="Other"))


def _apply_unique_ids(qre: Questionnaire, question_id: str, section_type: str) -> None:
    count = 0
    for section in qre.sections:
        for q in section.questions:
            if q.question_id == question_id:
                count += 1
                if count > 1:
                    q.question_id = f"{question_id}_{section.section_type[:3].upper()}_{count}"
                    q.var_name = q.question_id


def _apply_likert_scale(qre: Questionnaire, section_type: str) -> None:
    for section in qre.sections:
        if section.section_type == section_type:
            for q in section.questions:
                if q.question_type == QuestionType.LIKERT_SCALE:
                    q.scale_points = 5
                    q.scale_labels = {1: "Strongly Disagree", 2: "Disagree", 3: "Neutral", 4: "Agree", 5: "Strongly Agree"}


def _apply_var_name(qre: Questionnaire, question_id: str, section_type: str) -> None:
    for section in qre.sections:
        if section.section_type == section_type:
            for i, q in enumerate(section.questions):
                if q.question_id == question_id:
                    prefix = section_type[:3].upper()
                    q.var_name = f"{prefix}_{i+1:02d}"


_FIX_APPLIERS: dict[str, Callable] = {
    "screener_termination": lambda qre, p: _apply_screener_termination(qre),
    "response_codes_exhaustive": lambda qre, p: _apply_response_codes(qre, p.question_id or ""),
    "unique_question_ids": lambda qre, p: _apply_unique_ids(qre, p.question_id or "", p.section_type or ""),
    "likert_uniform_scale": lambda qre, p: _apply_likert_scale(qre, p.section_type or ""),
    "question_var_name": lambda qre, p: _apply_var_name(qre, p.question_id or "", p.section_type or ""),
}


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def generate_fix_proposals(report: ValidationReport, qre: Questionnaire) -> FixSession:
    """Generate fix proposals for all errors in a validation report."""
    proposals: list[FixProposal] = []
    for issue in report.errors():
        gen = _FIX_GENERATORS.get(issue.check_name)
        if gen:
            proposals.append(gen(issue, qre))
    return FixSession(
        questionnaire_id=report.questionnaire_id,
        version=report.version,
        proposals=proposals,
    )


def resolve_proposal(session: FixSession, fix_id: str, decision: FixStatus) -> FixProposal:
    """Accept or reject a specific fix proposal."""
    if decision not in (FixStatus.ACCEPTED, FixStatus.REJECTED):
        raise ValueError(f"Decision must be accepted or rejected, got {decision.value}")
    for p in session.proposals:
        if p.fix_id == fix_id:
            p.status = decision
            return p
    raise ValueError(f"Fix {fix_id!r} not found in session.")


def apply_accepted_fixes(session: FixSession, qre: Questionnaire) -> ValidationReport:
    """Apply all accepted fixes to the questionnaire and re-validate.

    Returns the new validation report after fixes are applied.
    """
    for proposal in session.accepted():
        applier = _FIX_APPLIERS.get(proposal.check_name)
        if applier:
            applier(qre, proposal)
            proposal.status = FixStatus.APPLIED

    # Re-validate automatically (AC-3)
    report = validate_questionnaire(qre)
    session.revalidation_report = report
    return report
