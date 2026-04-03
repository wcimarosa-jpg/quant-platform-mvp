"""Table QA copilot.

Explains QA findings in plain language, suggests corrective actions,
and logs user decisions on each finding.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .table_qa import QAFinding, QAReport, QASeverity


class ActionType(str, Enum):
    SUPPRESS_CELL = "suppress_cell"
    MERGE_SEGMENTS = "merge_segments"
    ADD_FOOTNOTE = "add_footnote"
    RECHECK_MAPPING = "recheck_mapping"
    ACCEPT_AS_IS = "accept_as_is"
    REMOVE_COLUMN = "remove_column"
    FILTER_DATA = "filter_data"


class DecisionStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class QAExplanation(BaseModel):
    """Plain-language explanation of one QA finding."""

    finding_id: str
    severity: str
    check_name: str
    table_id: str
    variable_name: str
    explanation: str
    impact: str


class SuggestedAction(BaseModel):
    """One suggested corrective action for a QA finding."""

    action_id: str = Field(default_factory=lambda: f"act-{uuid.uuid4().hex[:8]}")
    finding_id: str
    action_type: ActionType
    description: str
    status: DecisionStatus = DecisionStatus.PENDING


class QACopilotSession(BaseModel):
    """A copilot session for one QA report."""

    session_id: str = Field(default_factory=lambda: f"qacs-{uuid.uuid4().hex[:8]}")
    report_id: str
    run_id: str
    explanations: list[QAExplanation]
    actions: list[SuggestedAction]
    decisions: list[dict[str, Any]] = Field(default_factory=list)

    def pending_actions(self) -> list[SuggestedAction]:
        return [a for a in self.actions if a.status == DecisionStatus.PENDING]

    def all_resolved(self) -> bool:
        return len(self.pending_actions()) == 0


# ---------------------------------------------------------------------------
# Explanation generation — grounded in QA report fields
# ---------------------------------------------------------------------------

_CHECK_EXPLANATIONS: dict[str, dict[str, str]] = {
    "base_size": {
        "template": "The base size ({detail}) is below the minimum threshold. Results from this cell are not statistically reliable.",
        "impact": "Any percentages or significance tests in this cell are unreliable and should not be reported to stakeholders.",
    },
    "zero_base": {
        "template": "This cell has zero respondents. No data exists for this segment/variable combination.",
        "impact": "This cell cannot produce any meaningful statistics. It indicates a gap in the data or an empty segment.",
    },
    "missing_value": {
        "template": "A computed value is missing for this cell. The data may not have been mapped correctly.",
        "impact": "This gap will appear as a blank in the output tables. Downstream analysis may fail or produce incomplete results.",
    },
    "percentage_sum": {
        "template": "The percentages in this column don't sum to approximately 100%. This suggests missing response codes or a calculation issue.",
        "impact": "Stakeholders may question data quality if percentages don't sum correctly.",
    },
    "suspicious_distribution": {
        "template": "All rows in this column have identical percentages. This is statistically unlikely and suggests a data or mapping error.",
        "impact": "Uniform distributions in survey data are almost always a sign of incorrect coding, mapping error, or test data.",
    },
    "empty_table": {
        "template": "This table has no data rows. The variable may not be mapped or may have no responses.",
        "impact": "This table cannot be included in deliverables. The variable needs investigation.",
    },
}


def _explain_finding(finding: QAFinding) -> QAExplanation:
    check_info = _CHECK_EXPLANATIONS.get(finding.check_name, {
        "template": finding.message,
        "impact": "Review this finding and determine appropriate action.",
    })

    detail = ""
    if finding.column and finding.row_label:
        detail = f"in table '{finding.variable_name}', column '{finding.column}', row '{finding.row_label}'"
    elif finding.column:
        detail = f"in table '{finding.variable_name}', column '{finding.column}'"
    else:
        detail = f"in table '{finding.variable_name}'"

    explanation = check_info["template"].format(detail=detail)

    return QAExplanation(
        finding_id=finding.finding_id,
        severity=finding.severity.value,
        check_name=finding.check_name,
        table_id=finding.table_id,
        variable_name=finding.variable_name,
        explanation=f"{explanation} ({detail})",
        impact=check_info["impact"],
    )


# ---------------------------------------------------------------------------
# Action suggestion — maps check types to executable actions
# ---------------------------------------------------------------------------

_CHECK_ACTIONS: dict[str, list[tuple[ActionType, str]]] = {
    "base_size": [
        (ActionType.SUPPRESS_CELL, "Suppress this cell and display '*' or 'n<30' instead of the value."),
        (ActionType.MERGE_SEGMENTS, "Merge this segment with an adjacent segment to increase the base size."),
        (ActionType.ADD_FOOTNOTE, "Keep the value but add a footnote: 'Caution: small base size'."),
    ],
    "zero_base": [
        (ActionType.REMOVE_COLUMN, "Remove this banner column from the table entirely."),
        (ActionType.MERGE_SEGMENTS, "Merge with an adjacent segment that has data."),
    ],
    "missing_value": [
        (ActionType.RECHECK_MAPPING, "Re-check the data mapping for this variable."),
        (ActionType.ACCEPT_AS_IS, "Accept the missing value — it will appear as blank in output."),
    ],
    "percentage_sum": [
        (ActionType.RECHECK_MAPPING, "Verify all response codes are mapped and no codes are missing."),
        (ActionType.ACCEPT_AS_IS, "Accept as rounding artifact if the sum is close to 100%."),
    ],
    "suspicious_distribution": [
        (ActionType.RECHECK_MAPPING, "Verify the data mapping and check the source data for this variable."),
        (ActionType.FILTER_DATA, "Check for straight-liners or test responses that may skew the distribution."),
    ],
    "empty_table": [
        (ActionType.RECHECK_MAPPING, "Verify the variable is correctly mapped to a data column."),
        (ActionType.REMOVE_COLUMN, "Remove this variable from the table generation config."),
    ],
}


def _suggest_actions(finding: QAFinding) -> list[SuggestedAction]:
    check_actions = _CHECK_ACTIONS.get(finding.check_name, [
        (ActionType.ACCEPT_AS_IS, "No specific action suggested. Review and decide."),
    ])
    return [
        SuggestedAction(
            finding_id=finding.finding_id,
            action_type=action_type,
            description=description,
        )
        for action_type, description in check_actions
    ]


# ---------------------------------------------------------------------------
# Main copilot analysis
# ---------------------------------------------------------------------------

def analyze_qa_report(report: QAReport) -> QACopilotSession:
    """Generate explanations and suggested actions for all QA findings."""
    explanations = [_explain_finding(f) for f in report.findings]
    actions: list[SuggestedAction] = []
    for f in report.findings:
        actions.extend(_suggest_actions(f))

    return QACopilotSession(
        report_id=report.report_id,
        run_id=report.run_id,
        explanations=explanations,
        actions=actions,
    )


# ---------------------------------------------------------------------------
# Decision logging
# ---------------------------------------------------------------------------

def resolve_action(
    session: QACopilotSession,
    action_id: str,
    decision: DecisionStatus,
    user_note: str = "",
) -> SuggestedAction:
    """Accept or reject a suggested action, logging the decision."""
    if decision == DecisionStatus.PENDING:
        raise ValueError("Cannot set status back to pending.")
    for a in session.actions:
        if a.action_id == action_id:
            a.status = decision
            session.decisions.append({
                "action_id": action_id,
                "finding_id": a.finding_id,
                "action_type": a.action_type.value,
                "decision": decision.value,
                "user_note": user_note,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            })
            return a
    raise ValueError(f"Action {action_id!r} not found.")
