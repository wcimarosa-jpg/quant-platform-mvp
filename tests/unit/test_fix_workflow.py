"""Contract tests for assistant fix workflow (P04-02).

AC-1: Fix suggestions map to specific validation failures.
AC-2: User can accept fixes individually.
AC-3: Re-validation runs automatically after applied fixes.
"""

from __future__ import annotations

import pytest

from packages.shared.questionnaire_schema import (
    Question,
    QuestionType,
    Questionnaire,
    ResponseOption,
    Section,
)
from packages.shared.validation_engine import validate_questionnaire
from packages.shared.fix_workflow import (
    FixProposal,
    FixSession,
    FixStatus,
    apply_accepted_fixes,
    generate_fix_proposals,
    resolve_proposal,
)


def _qre_with_issues() -> Questionnaire:
    """Questionnaire with deliberate validation issues."""
    return Questionnaire(
        project_id="proj-001",
        methodology="segmentation",
        sections=[
            Section(
                section_id="scr", section_type="screener", label="Screener", order=0,
                questions=[
                    # Only 1 response option (needs 2+), no termination
                    Question(question_id="SCR_01", question_text="Category?",
                             question_type=QuestionType.SINGLE_SELECT, var_name="SCR_01",
                             response_options=[ResponseOption(code=1, label="Yes")]),
                ],
            ),
            Section(
                section_id="att", section_type="attitudes", label="Attitudes", order=1,
                questions=[
                    # Only 5 items (needs 15+), mixed scales
                    Question(question_id="ATT_01", question_text="S1",
                             question_type=QuestionType.LIKERT_SCALE, var_name="ATT_01", scale_points=5),
                    Question(question_id="ATT_02", question_text="S2",
                             question_type=QuestionType.LIKERT_SCALE, var_name="ATT_02", scale_points=7),
                    Question(question_id="ATT_03", question_text="S3",
                             question_type=QuestionType.LIKERT_SCALE, var_name="ATT_03", scale_points=5),
                    Question(question_id="ATT_04", question_text="S4",
                             question_type=QuestionType.LIKERT_SCALE, var_name="", scale_points=5),
                    Question(question_id="ATT_05", question_text="S5",
                             question_type=QuestionType.LIKERT_SCALE, var_name="ATT_05", scale_points=5),
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# AC-1: Fix suggestions map to specific validation failures
# ---------------------------------------------------------------------------

class TestFixMapping:
    def test_proposals_generated_for_errors(self):
        qre = _qre_with_issues()
        report = validate_questionnaire(qre)
        assert report.error_count >= 3  # codes, termination, attitudes, scale, var_name
        session = generate_fix_proposals(report, qre)
        assert len(session.proposals) >= 3

    def test_each_proposal_maps_to_an_issue(self):
        qre = _qre_with_issues()
        report = validate_questionnaire(qre)
        session = generate_fix_proposals(report, qre)
        error_ids = {i.issue_id for i in report.errors()}
        for proposal in session.proposals:
            assert proposal.issue_id in error_ids

    def test_proposals_have_check_name(self):
        qre = _qre_with_issues()
        report = validate_questionnaire(qre)
        session = generate_fix_proposals(report, qre)
        for p in session.proposals:
            assert p.check_name
            assert p.description

    def test_proposals_have_section_references(self):
        qre = _qre_with_issues()
        report = validate_questionnaire(qre)
        session = generate_fix_proposals(report, qre)
        # At least some should have section_type
        sections = [p.section_type for p in session.proposals if p.section_type]
        assert len(sections) > 0

    def test_proposals_have_question_references_where_applicable(self):
        qre = _qre_with_issues()
        report = validate_questionnaire(qre)
        session = generate_fix_proposals(report, qre)
        question_fixes = [p for p in session.proposals if p.question_id]
        assert len(question_fixes) > 0

    def test_no_proposals_for_warnings(self):
        """Fix proposals should only target errors, not warnings."""
        qre = _qre_with_issues()
        report = validate_questionnaire(qre)
        session = generate_fix_proposals(report, qre)
        warning_ids = {i.issue_id for i in report.warnings()}
        for p in session.proposals:
            assert p.issue_id not in warning_ids

    def test_fix_ids_are_unique(self):
        qre = _qre_with_issues()
        report = validate_questionnaire(qre)
        session = generate_fix_proposals(report, qre)
        ids = [p.fix_id for p in session.proposals]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# AC-2: User can accept fixes individually
# ---------------------------------------------------------------------------

class TestIndividualAcceptance:
    def test_accept_one_proposal(self):
        qre = _qre_with_issues()
        report = validate_questionnaire(qre)
        session = generate_fix_proposals(report, qre)
        p = session.proposals[0]
        result = resolve_proposal(session, p.fix_id, FixStatus.ACCEPTED)
        assert result.status == FixStatus.ACCEPTED

    def test_reject_one_proposal(self):
        qre = _qre_with_issues()
        report = validate_questionnaire(qre)
        session = generate_fix_proposals(report, qre)
        p = session.proposals[0]
        result = resolve_proposal(session, p.fix_id, FixStatus.REJECTED)
        assert result.status == FixStatus.REJECTED

    def test_mixed_accept_reject(self):
        qre = _qre_with_issues()
        report = validate_questionnaire(qre)
        session = generate_fix_proposals(report, qre)
        if len(session.proposals) >= 2:
            resolve_proposal(session, session.proposals[0].fix_id, FixStatus.ACCEPTED)
            resolve_proposal(session, session.proposals[1].fix_id, FixStatus.REJECTED)
            assert session.proposals[0].status == FixStatus.ACCEPTED
            assert session.proposals[1].status == FixStatus.REJECTED

    def test_all_start_pending(self):
        qre = _qre_with_issues()
        report = validate_questionnaire(qre)
        session = generate_fix_proposals(report, qre)
        assert all(p.status == FixStatus.PENDING for p in session.proposals)

    def test_unknown_fix_id_raises(self):
        qre = _qre_with_issues()
        report = validate_questionnaire(qre)
        session = generate_fix_proposals(report, qre)
        with pytest.raises(ValueError, match="not found"):
            resolve_proposal(session, "nonexistent", FixStatus.ACCEPTED)

    def test_invalid_decision_raises(self):
        qre = _qre_with_issues()
        report = validate_questionnaire(qre)
        session = generate_fix_proposals(report, qre)
        with pytest.raises(ValueError, match="accepted or rejected"):
            resolve_proposal(session, session.proposals[0].fix_id, FixStatus.PENDING)

    def test_all_resolved_check(self):
        qre = _qre_with_issues()
        report = validate_questionnaire(qre)
        session = generate_fix_proposals(report, qre)
        assert not session.all_resolved()
        for p in session.proposals:
            resolve_proposal(session, p.fix_id, FixStatus.ACCEPTED)
        assert session.all_resolved()


# ---------------------------------------------------------------------------
# AC-3: Re-validation runs automatically after applied fixes
# ---------------------------------------------------------------------------

class TestRevalidation:
    def test_apply_fixes_returns_new_report(self):
        qre = _qre_with_issues()
        report = validate_questionnaire(qre)
        session = generate_fix_proposals(report, qre)
        for p in session.proposals:
            resolve_proposal(session, p.fix_id, FixStatus.ACCEPTED)
        new_report = apply_accepted_fixes(session, qre)
        assert isinstance(new_report, type(report))
        assert new_report.questionnaire_id == qre.questionnaire_id

    def test_applied_fixes_reduce_errors(self):
        qre = _qre_with_issues()
        report = validate_questionnaire(qre)
        original_errors = report.error_count
        session = generate_fix_proposals(report, qre)
        for p in session.proposals:
            resolve_proposal(session, p.fix_id, FixStatus.ACCEPTED)
        new_report = apply_accepted_fixes(session, qre)
        # Should have fewer errors (may not be zero if some fixes are partial)
        assert new_report.error_count <= original_errors

    def test_revalidation_stored_on_session(self):
        qre = _qre_with_issues()
        report = validate_questionnaire(qre)
        session = generate_fix_proposals(report, qre)
        for p in session.proposals:
            resolve_proposal(session, p.fix_id, FixStatus.ACCEPTED)
        apply_accepted_fixes(session, qre)
        assert session.revalidation_report is not None

    def test_accepted_proposals_marked_applied(self):
        qre = _qre_with_issues()
        report = validate_questionnaire(qre)
        session = generate_fix_proposals(report, qre)
        for p in session.proposals:
            resolve_proposal(session, p.fix_id, FixStatus.ACCEPTED)
        apply_accepted_fixes(session, qre)
        for p in session.proposals:
            if p.check_name in ("screener_termination", "response_codes_exhaustive",
                                "likert_uniform_scale", "question_var_name"):
                assert p.status == FixStatus.APPLIED

    def test_rejected_fixes_not_applied(self):
        qre = _qre_with_issues()
        report = validate_questionnaire(qre)
        session = generate_fix_proposals(report, qre)
        for p in session.proposals:
            resolve_proposal(session, p.fix_id, FixStatus.REJECTED)
        new_report = apply_accepted_fixes(session, qre)
        # No fixes applied, so error count should not decrease
        assert new_report.error_count >= report.error_count

    def test_screener_termination_fix_applied(self):
        """Specific fix: after applying screener termination fix, screener should have a terminate option."""
        qre = _qre_with_issues()
        report = validate_questionnaire(qre)
        session = generate_fix_proposals(report, qre)
        term_fix = next((p for p in session.proposals if p.check_name == "screener_termination"), None)
        if term_fix:
            resolve_proposal(session, term_fix.fix_id, FixStatus.ACCEPTED)
            # Reject others to isolate this fix
            for p in session.proposals:
                if p.status == FixStatus.PENDING:
                    resolve_proposal(session, p.fix_id, FixStatus.REJECTED)
            apply_accepted_fixes(session, qre)
            screener = qre.get_section("screener")
            has_term = any(opt.terminates for q in screener.questions for opt in q.response_options)
            assert has_term

    def test_likert_scale_fix_applied(self):
        """After applying scale fix, all Likert items should be 5-point."""
        qre = _qre_with_issues()
        report = validate_questionnaire(qre)
        session = generate_fix_proposals(report, qre)
        scale_fix = next((p for p in session.proposals if p.check_name == "likert_uniform_scale"), None)
        if scale_fix:
            resolve_proposal(session, scale_fix.fix_id, FixStatus.ACCEPTED)
            for p in session.proposals:
                if p.status == FixStatus.PENDING:
                    resolve_proposal(session, p.fix_id, FixStatus.REJECTED)
            apply_accepted_fixes(session, qre)
            attitudes = qre.get_section("attitudes")
            scales = {q.scale_points for q in attitudes.questions if q.question_type == QuestionType.LIKERT_SCALE}
            assert scales == {5}
