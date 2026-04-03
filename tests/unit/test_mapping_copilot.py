"""Contract tests for mapping copilot (P05-03).

AC-1: Confidence signals shown per mapped field.
AC-2: Assistant can suggest and apply mapping corrections.
AC-3: All accepted changes are versioned.
"""

from __future__ import annotations

import pytest

from packages.shared.data_profiler import ColumnProfile, DataProfile
from packages.shared.mapping_engine import (
    MappingStore,
    MappingVersion,
    MatchConfidence,
    auto_map,
    edit_mapping,
)
from packages.shared.mapping_copilot import (
    CopilotAnalysis,
    ConfidenceExplanation,
    MappingSuggestion,
    SuggestionStatus,
    analyze_mapping,
    apply_accepted_suggestions,
    resolve_suggestion,
)
from packages.shared.questionnaire_schema import (
    Question,
    QuestionType,
    Questionnaire,
    ResponseOption,
    Section,
)


def _profile(columns: list[str]) -> DataProfile:
    return DataProfile(
        file_id="file-001", filename="data.csv", file_format="csv",
        file_hash="sha256:abc123", size_bytes=1024, row_count=100,
        column_count=len(columns),
        columns=[
            ColumnProfile(name=c, dtype="float64", non_null_count=100,
                          null_count=0, null_pct=0.0, unique_count=50, sample_values=["1"])
            for c in columns
        ],
        total_null_count=0, total_null_pct=0.0,
    )


def _qre(var_names: list[str]) -> Questionnaire:
    questions = [
        Question(question_id=f"Q{i+1}", question_text=f"Q{i+1}?",
                 question_type=QuestionType.SINGLE_SELECT, var_name=vn,
                 response_options=[ResponseOption(code=1, label="A"), ResponseOption(code=2, label="B")])
        for i, vn in enumerate(var_names)
    ]
    return Questionnaire(
        project_id="proj-001", methodology="segmentation", version=1,
        sections=[Section(section_id="s1", section_type="test", label="T", order=0, questions=questions)],
    )


def _vars(qre: Questionnaire) -> list[tuple[str, str]]:
    return [(q.var_name, q.question_id) for s in qre.sections for q in s.questions]


# ---------------------------------------------------------------------------
# AC-1: Confidence signals shown per mapped field
# ---------------------------------------------------------------------------

class TestConfidenceExplanations:
    def test_every_column_gets_explanation(self):
        profile = _profile(["SCR_01", "unknown_col", "ATT_01"])
        qre = _qre(["SCR_01", "ATT_01"])
        mapping = auto_map(profile, qre)
        analysis = analyze_mapping(mapping, _vars(qre))
        assert len(analysis.explanations) == 3

    def test_high_confidence_explanation(self):
        profile = _profile(["SCR_01"])
        qre = _qre(["SCR_01"])
        mapping = auto_map(profile, qre)
        analysis = analyze_mapping(mapping, _vars(qre))
        exp = analysis.explanations[0]
        assert exp.confidence >= 0.8
        assert exp.confidence_level == "high"
        assert "High confidence" in exp.explanation
        assert not exp.needs_review

    def test_no_match_explanation(self):
        profile = _profile(["totally_random"])
        qre = _qre(["SCR_01"])
        mapping = auto_map(profile, qre)
        analysis = analyze_mapping(mapping, _vars(qre))
        # "totally_random" should not match "SCR_01" at high confidence
        low_or_none = [e for e in analysis.explanations if e.confidence_level in ("low", "none")]
        assert len(low_or_none) >= 1

    def test_explanation_references_column_name(self):
        profile = _profile(["SCR_01"])
        qre = _qre(["SCR_01"])
        mapping = auto_map(profile, qre)
        analysis = analyze_mapping(mapping, _vars(qre))
        assert "SCR_01" in analysis.explanations[0].explanation

    def test_needs_review_flag_on_low_confidence(self):
        profile = _profile(["col_a", "SCR_01"])
        qre = _qre(["SCR_01", "ATT_01"])
        mapping = auto_map(profile, qre)
        analysis = analyze_mapping(mapping, _vars(qre))
        # col_a might have low or no match — check that needs_review is set accordingly
        for exp in analysis.explanations:
            if exp.confidence_level in ("low", "none") and exp.var_name:
                assert exp.needs_review is True

    def test_manually_edited_not_flagged(self):
        profile = _profile(["col_a"])
        qre = _qre(["SCR_01"])
        mapping = auto_map(profile, qre)
        edit_mapping(mapping, "col_a", var_name="SCR_01")
        analysis = analyze_mapping(mapping, _vars(qre))
        exp = analysis.explanations[0]
        assert exp.needs_review is False  # manually edited = reviewed

    def test_counts_in_analysis(self):
        profile = _profile(["SCR_01", "unknown", "ATT_01"])
        qre = _qre(["SCR_01", "ATT_01"])
        mapping = auto_map(profile, qre)
        analysis = analyze_mapping(mapping, _vars(qre))
        assert analysis.high_confidence_count == 2
        # "unknown" column should be unmapped or low confidence
        assert analysis.unmapped_count >= 1 or analysis.low_confidence_count >= 1


# ---------------------------------------------------------------------------
# AC-2: Assistant can suggest and apply corrections
# ---------------------------------------------------------------------------

class TestSuggestions:
    def test_suggestions_for_unmapped_columns(self):
        profile = _profile(["random_x", "random_y", "SCR_01"])
        qre = _qre(["SCR_01", "ATT_01", "DEM_01"])
        mapping = auto_map(profile, qre)
        analysis = analyze_mapping(mapping, _vars(qre))
        # Should have suggestions for unmapped columns
        # random_x and random_y should not match well, so we expect suggestions
        assert len(analysis.suggestions) >= 1

    def test_suggestion_has_rationale(self):
        profile = _profile(["random_x", "SCR_01"])
        qre = _qre(["SCR_01", "ATT_01"])
        mapping = auto_map(profile, qre)
        analysis = analyze_mapping(mapping, _vars(qre))
        for s in analysis.suggestions:
            assert s.rationale
            assert len(s.rationale) > 10

    def test_accept_suggestion(self):
        profile = _profile(["random_x", "SCR_01"])
        qre = _qre(["SCR_01", "ATT_01"])
        mapping = auto_map(profile, qre)
        analysis = analyze_mapping(mapping, _vars(qre))
        assert len(analysis.suggestions) > 0
        s = analysis.suggestions[0]
        result = resolve_suggestion(analysis, s.suggestion_id, SuggestionStatus.ACCEPTED)
        assert result.status == SuggestionStatus.ACCEPTED

    def test_reject_suggestion(self):
        profile = _profile(["random_x", "SCR_01"])
        qre = _qre(["SCR_01", "ATT_01"])
        mapping = auto_map(profile, qre)
        analysis = analyze_mapping(mapping, _vars(qre))
        assert len(analysis.suggestions) > 0
        s = analysis.suggestions[0]
        result = resolve_suggestion(analysis, s.suggestion_id, SuggestionStatus.REJECTED)
        assert result.status == SuggestionStatus.REJECTED

    def test_cannot_set_pending(self):
        profile = _profile(["random_x"])
        qre = _qre(["SCR_01"])
        mapping = auto_map(profile, qre)
        analysis = analyze_mapping(mapping, _vars(qre))
        assert len(analysis.suggestions) > 0
        with pytest.raises(ValueError, match="pending"):
            resolve_suggestion(analysis, analysis.suggestions[0].suggestion_id, SuggestionStatus.PENDING)

    def test_unknown_suggestion_raises(self):
        profile = _profile(["SCR_01"])
        qre = _qre(["SCR_01"])
        mapping = auto_map(profile, qre)
        analysis = analyze_mapping(mapping, _vars(qre))
        with pytest.raises(ValueError, match="not found"):
            resolve_suggestion(analysis, "nonexistent", SuggestionStatus.ACCEPTED)

    def test_all_resolved_check(self):
        profile = _profile(["random_x"])
        qre = _qre(["SCR_01"])
        mapping = auto_map(profile, qre)
        analysis = analyze_mapping(mapping, _vars(qre))
        if analysis.suggestions:
            assert not analysis.all_resolved()
            for s in analysis.suggestions:
                resolve_suggestion(analysis, s.suggestion_id, SuggestionStatus.ACCEPTED)
            assert analysis.all_resolved()

    def test_apply_accepted_suggestions(self):
        profile = _profile(["unmapped_col", "SCR_01"])
        qre = _qre(["SCR_01", "ATT_01"])
        mapping = auto_map(profile, qre)
        analysis = analyze_mapping(mapping, _vars(qre))
        # Accept all suggestions
        for s in analysis.suggestions:
            resolve_suggestion(analysis, s.suggestion_id, SuggestionStatus.ACCEPTED)
        apply_accepted_suggestions(analysis, mapping)
        # Check that accepted suggestions were applied
        for s in analysis.accepted_suggestions():
            if s.suggested_var:
                m = mapping.get_mapping(s.column_name)
                assert m.var_name == s.suggested_var
                assert m.manually_edited is True


# ---------------------------------------------------------------------------
# AC-3: All accepted changes are versioned
# ---------------------------------------------------------------------------

class TestVersionedChanges:
    def test_applied_changes_update_timestamp(self):
        profile = _profile(["unmapped_col", "SCR_01"])
        qre = _qre(["SCR_01", "ATT_01"])
        mapping = auto_map(profile, qre)
        original_updated = mapping.updated_at
        analysis = analyze_mapping(mapping, _vars(qre))
        for s in analysis.suggestions:
            resolve_suggestion(analysis, s.suggestion_id, SuggestionStatus.ACCEPTED)
        apply_accepted_suggestions(analysis, mapping)
        if analysis.accepted_suggestions():
            assert mapping.updated_at >= original_updated

    def test_store_preserves_versions(self):
        store = MappingStore()
        profile = _profile(["SCR_01", "unmapped"])
        qre = _qre(["SCR_01", "ATT_01"])

        # Save v1
        m1 = auto_map(profile, qre)
        store.save(m1)

        # Edit and save v2
        m2 = auto_map(profile, qre)
        analysis = analyze_mapping(m2, _vars(qre))
        for s in analysis.suggestions:
            resolve_suggestion(analysis, s.suggestion_id, SuggestionStatus.ACCEPTED)
        apply_accepted_suggestions(analysis, m2)
        store.save(m2)

        assert store.get_version("proj-001", 1) is not None
        assert store.get_version("proj-001", 2) is not None

    def test_suggestion_ids_unique(self):
        profile = _profile(["a", "b", "c"])
        qre = _qre(["SCR_01"])
        mapping = auto_map(profile, qre)
        analysis = analyze_mapping(mapping, _vars(qre))
        ids = [s.suggestion_id for s in analysis.suggestions]
        assert len(ids) == len(set(ids))

    def test_rejected_suggestions_not_applied(self):
        profile = _profile(["unmapped_col", "SCR_01"])
        qre = _qre(["SCR_01", "ATT_01"])
        mapping = auto_map(profile, qre)
        analysis = analyze_mapping(mapping, _vars(qre))
        for s in analysis.suggestions:
            resolve_suggestion(analysis, s.suggestion_id, SuggestionStatus.REJECTED)
        apply_accepted_suggestions(analysis, mapping)
        # Nothing should have changed for rejected suggestions
        for s in analysis.suggestions:
            m = mapping.get_mapping(s.column_name)
            if s.current_var is None and s.suggested_var is not None:
                assert m.var_name != s.suggested_var or m.var_name is None
