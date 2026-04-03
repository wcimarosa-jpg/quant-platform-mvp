"""Mapping copilot with confidence explanations.

Analyzes auto-mappings, explains low-confidence matches,
suggests corrections, and applies user-approved fixes
as versioned edits.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .mapping_engine import (
    ColumnMapping,
    MappingStore,
    MappingVersion,
    MatchConfidence,
    edit_mapping,
)


class SuggestionStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ConfidenceExplanation(BaseModel):
    """Human-readable explanation of a mapping's confidence level."""

    column_name: str
    var_name: str | None
    confidence: float
    confidence_level: str
    explanation: str
    needs_review: bool


class MappingSuggestion(BaseModel):
    """One suggested correction for a mapping."""

    suggestion_id: str = Field(default_factory=lambda: f"sug-{uuid.uuid4().hex[:8]}")
    column_name: str
    current_var: str | None
    suggested_var: str | None
    suggested_question_id: str | None = None
    rationale: str
    status: SuggestionStatus = SuggestionStatus.PENDING


class CopilotAnalysis(BaseModel):
    """Complete copilot analysis of a mapping version."""

    analysis_id: str = Field(default_factory=lambda: f"copa-{uuid.uuid4().hex[:8]}")
    mapping_id: str
    mapping_version: int
    explanations: list[ConfidenceExplanation]
    suggestions: list[MappingSuggestion]
    high_confidence_count: int
    low_confidence_count: int
    unmapped_count: int

    def pending_suggestions(self) -> list[MappingSuggestion]:
        return [s for s in self.suggestions if s.status == SuggestionStatus.PENDING]

    def accepted_suggestions(self) -> list[MappingSuggestion]:
        return [s for s in self.suggestions if s.status == SuggestionStatus.ACCEPTED]

    def all_resolved(self) -> bool:
        return len(self.pending_suggestions()) == 0


# ---------------------------------------------------------------------------
# Confidence explanation generation
# ---------------------------------------------------------------------------

_CONFIDENCE_EXPLANATIONS = {
    MatchConfidence.HIGH: "High confidence: {reason}. Column '{col}' closely matches variable '{var}'.",
    MatchConfidence.MEDIUM: "Medium confidence: {reason}. Column '{col}' partially matches variable '{var}'. Review recommended.",
    MatchConfidence.LOW: "Low confidence: {reason}. Column '{col}' has a weak match to variable '{var}'. Likely needs correction.",
    MatchConfidence.NONE: "No match found for column '{col}'. Manual mapping required.",
}


def _explain_mapping(m: ColumnMapping) -> ConfidenceExplanation:
    level = m.confidence_level
    if m.var_name and level != MatchConfidence.NONE:
        template = _CONFIDENCE_EXPLANATIONS[level]
        explanation = template.format(col=m.column_name, var=m.var_name, reason=m.match_reason)
    else:
        explanation = _CONFIDENCE_EXPLANATIONS[MatchConfidence.NONE].format(col=m.column_name)

    return ConfidenceExplanation(
        column_name=m.column_name,
        var_name=m.var_name,
        confidence=round(m.confidence, 2),
        confidence_level=level.value,
        explanation=explanation,
        needs_review=level in (MatchConfidence.LOW, MatchConfidence.NONE) and not m.manually_edited,
    )


# ---------------------------------------------------------------------------
# Suggestion generation
# ---------------------------------------------------------------------------

def _generate_suggestions(
    mapping: MappingVersion,
    available_vars: list[tuple[str, str]],
) -> list[MappingSuggestion]:
    """Generate correction suggestions for low-confidence and unmapped columns."""
    suggestions: list[MappingSuggestion] = []
    mapped_vars = {m.var_name for m in mapping.mappings if m.var_name}
    suggested_vars: set[str] = set()  # track vars already suggested to avoid duplicates

    for m in mapping.mappings:
        if m.manually_edited:
            continue

        if m.confidence_level == MatchConfidence.LOW and m.var_name:
            suggestions.append(MappingSuggestion(
                column_name=m.column_name,
                current_var=m.var_name,
                suggested_var=None,
                rationale=f"Low confidence match ({m.match_reason}). Consider unmapping or selecting the correct variable.",
            ))

        elif m.confidence_level == MatchConfidence.NONE:
            # Try to find an unmapped variable not already suggested
            best_var = None
            best_qid = None
            for var_name, qid in available_vars:
                if var_name not in mapped_vars and var_name not in suggested_vars:
                    best_var = var_name
                    best_qid = qid
                    break

            if best_var:
                suggested_vars.add(best_var)
                suggestions.append(MappingSuggestion(
                    column_name=m.column_name,
                    current_var=None,
                    suggested_var=best_var,
                    suggested_question_id=best_qid,
                    rationale=f"Column '{m.column_name}' is unmapped. Variable '{best_var}' is available and unassigned.",
                ))
            else:
                suggestions.append(MappingSuggestion(
                    column_name=m.column_name,
                    current_var=None,
                    suggested_var=None,
                    rationale=f"Column '{m.column_name}' is unmapped and no unassigned variables remain. May be a data-only column.",
                ))

    return suggestions


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def analyze_mapping(
    mapping: MappingVersion,
    questionnaire_vars: list[tuple[str, str]],
) -> CopilotAnalysis:
    """Run copilot analysis on a mapping version.

    Args:
        mapping: The mapping version to analyze.
        questionnaire_vars: List of (var_name, question_id) from the questionnaire.
    """
    explanations = [_explain_mapping(m) for m in mapping.mappings]
    suggestions = _generate_suggestions(mapping, questionnaire_vars)

    return CopilotAnalysis(
        mapping_id=mapping.mapping_id,
        mapping_version=mapping.version,
        explanations=explanations,
        suggestions=suggestions,
        high_confidence_count=mapping.high_confidence_count(),
        low_confidence_count=len(mapping.low_confidence_mappings()),
        unmapped_count=len(mapping.unmapped_columns),
    )


# ---------------------------------------------------------------------------
# Suggestion resolution
# ---------------------------------------------------------------------------

def resolve_suggestion(
    analysis: CopilotAnalysis,
    suggestion_id: str,
    decision: SuggestionStatus,
) -> MappingSuggestion:
    """Accept or reject a suggestion."""
    if decision == SuggestionStatus.PENDING:
        raise ValueError("Cannot set status back to pending.")
    for s in analysis.suggestions:
        if s.suggestion_id == suggestion_id:
            s.status = decision
            return s
    raise ValueError(f"Suggestion {suggestion_id!r} not found.")


def apply_accepted_suggestions(
    analysis: CopilotAnalysis,
    mapping: MappingVersion,
) -> MappingVersion:
    """Apply all accepted suggestions to the mapping.

    Each accepted suggestion becomes an edit_mapping call.
    Returns the updated mapping version.
    """
    for s in analysis.accepted_suggestions():
        if s.suggested_var is not None:
            edit_mapping(mapping, s.column_name, s.suggested_var, s.suggested_question_id)
        elif s.current_var is not None and s.suggested_var is None:
            # Suggestion was to unmap — only if user explicitly accepted
            edit_mapping(mapping, s.column_name, None)

    return mapping
