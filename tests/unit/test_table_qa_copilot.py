"""Contract tests for table QA copilot (P06-03).

AC-1: Assistant explanations reference QA report fields.
AC-2: Suggested actions are executable from UI.
AC-3: User decisions are logged.
"""

from __future__ import annotations

import pytest

from packages.survey_analysis.table_qa import (
    QAFinding,
    QAReport,
    QASeverity,
)
from packages.survey_analysis.table_qa_copilot import (
    ActionType,
    DecisionStatus,
    QACopilotSession,
    QAExplanation,
    SuggestedAction,
    analyze_qa_report,
    resolve_action,
)


def _report_with_findings() -> QAReport:
    return QAReport(
        run_id="tblrun-001",
        project_id="proj-001",
        findings=[
            QAFinding(
                finding_id="qaf-001",
                severity=QASeverity.ERROR,
                check_name="base_size",
                table_id="tbl-001",
                variable_name="SCR_01",
                column="Seg A",
                row_label="Option 1",
                message="Base size 10 below minimum 30.",
                remediation="Suppress cell or merge segments.",
            ),
            QAFinding(
                finding_id="qaf-002",
                severity=QASeverity.WARNING,
                check_name="suspicious_distribution",
                table_id="tbl-002",
                variable_name="ATT_01",
                column="Total",
                message="All rows identical at 25.0%.",
                remediation="Verify data mapping.",
            ),
            QAFinding(
                finding_id="qaf-003",
                severity=QASeverity.ERROR,
                check_name="zero_base",
                table_id="tbl-003",
                variable_name="DEM_01",
                column="Empty Seg",
                row_label="Male",
                message="Zero base in Empty Seg.",
                remediation="Remove or merge segment.",
            ),
        ],
        checks_run=18,
    )


def _empty_report() -> QAReport:
    return QAReport(run_id="tblrun-002", project_id="proj-001")


# ---------------------------------------------------------------------------
# AC-1: Explanations reference QA report fields
# ---------------------------------------------------------------------------

class TestExplanations:
    def test_explanation_per_finding(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        assert len(session.explanations) == 3

    def test_explanation_references_finding_id(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        finding_ids = {f.finding_id for f in report.findings}
        for exp in session.explanations:
            assert exp.finding_id in finding_ids

    def test_explanation_references_variable(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        assert session.explanations[0].variable_name == "SCR_01"
        assert session.explanations[1].variable_name == "ATT_01"

    def test_explanation_references_table_id(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        assert session.explanations[0].table_id == "tbl-001"

    def test_explanation_has_severity(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        assert session.explanations[0].severity == "error"
        assert session.explanations[1].severity == "warning"

    def test_explanation_has_check_name(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        assert session.explanations[0].check_name == "base_size"

    def test_explanation_text_is_specific(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        exp = session.explanations[0]
        assert "SCR_01" in exp.explanation
        assert "Seg A" in exp.explanation

    def test_explanation_has_impact(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        for exp in session.explanations:
            assert exp.impact
            assert len(exp.impact) > 10

    def test_empty_report_no_explanations(self):
        session = analyze_qa_report(_empty_report())
        assert len(session.explanations) == 0


# ---------------------------------------------------------------------------
# AC-2: Suggested actions are executable from UI
# ---------------------------------------------------------------------------

class TestSuggestedActions:
    def test_actions_generated_for_each_finding(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        assert len(session.actions) >= 3  # at least 1 per finding

    def test_base_size_has_multiple_actions(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        base_actions = [a for a in session.actions if a.finding_id == "qaf-001"]
        assert len(base_actions) >= 2  # suppress, merge, footnote
        action_types = {a.action_type for a in base_actions}
        assert ActionType.SUPPRESS_CELL in action_types
        assert ActionType.MERGE_SEGMENTS in action_types

    def test_actions_have_descriptions(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        for action in session.actions:
            assert action.description
            assert len(action.description) > 10

    def test_actions_have_action_type(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        for action in session.actions:
            assert action.action_type in ActionType

    def test_action_ids_unique(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        ids = [a.action_id for a in session.actions]
        assert len(ids) == len(set(ids))

    def test_all_actions_start_pending(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        assert all(a.status == DecisionStatus.PENDING for a in session.actions)

    def test_accept_action(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        assert len(session.actions) > 0
        a = session.actions[0]
        result = resolve_action(session, a.action_id, DecisionStatus.ACCEPTED)
        assert result.status == DecisionStatus.ACCEPTED

    def test_reject_action(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        assert len(session.actions) > 0
        a = session.actions[0]
        result = resolve_action(session, a.action_id, DecisionStatus.REJECTED)
        assert result.status == DecisionStatus.REJECTED

    def test_cannot_set_pending(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        with pytest.raises(ValueError, match="pending"):
            resolve_action(session, session.actions[0].action_id, DecisionStatus.PENDING)

    def test_unknown_action_raises(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        with pytest.raises(ValueError, match="not found"):
            resolve_action(session, "nonexistent", DecisionStatus.ACCEPTED)

    def test_all_resolved_check(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        assert not session.all_resolved()
        for a in session.actions:
            resolve_action(session, a.action_id, DecisionStatus.ACCEPTED)
        assert session.all_resolved()


# ---------------------------------------------------------------------------
# AC-3: User decisions are logged
# ---------------------------------------------------------------------------

class TestDecisionLogging:
    def test_decision_logged_on_accept(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        a = session.actions[0]
        resolve_action(session, a.action_id, DecisionStatus.ACCEPTED, user_note="Looks correct")
        assert len(session.decisions) == 1
        d = session.decisions[0]
        assert d["action_id"] == a.action_id
        assert d["decision"] == "accepted"
        assert d["user_note"] == "Looks correct"
        assert "timestamp" in d

    def test_decision_logged_on_reject(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        a = session.actions[0]
        resolve_action(session, a.action_id, DecisionStatus.REJECTED, user_note="Not needed")
        assert session.decisions[0]["decision"] == "rejected"

    def test_multiple_decisions_logged(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        for a in session.actions[:3]:
            resolve_action(session, a.action_id, DecisionStatus.ACCEPTED)
        assert len(session.decisions) == 3

    def test_decision_includes_finding_id(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        a = session.actions[0]
        resolve_action(session, a.action_id, DecisionStatus.ACCEPTED)
        assert session.decisions[0]["finding_id"] == a.finding_id

    def test_decision_includes_action_type(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        a = session.actions[0]
        resolve_action(session, a.action_id, DecisionStatus.ACCEPTED)
        assert session.decisions[0]["action_type"] == a.action_type.value

    def test_session_links_to_report(self):
        report = _report_with_findings()
        session = analyze_qa_report(report)
        assert session.report_id == report.report_id
        assert session.run_id == report.run_id
