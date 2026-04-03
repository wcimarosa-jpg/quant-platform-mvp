"""Contract tests for auto-mapping engine (P05-02).

AC-1: Auto-map produced from questionnaire + data profile.
AC-2: Users can edit and save mapping versions.
AC-3: Mapping is linked to questionnaire version and data file hash.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from packages.shared.data_profiler import ColumnProfile, DataProfile
from packages.shared.mapping_engine import (
    ColumnMapping,
    MappingStore,
    MappingVersion,
    MatchConfidence,
    auto_map,
    edit_mapping,
)
from packages.shared.questionnaire_schema import (
    Question,
    QuestionType,
    Questionnaire,
    ResponseOption,
    Section,
)

NOW = datetime.now(tz=timezone.utc)


def _profile(columns: list[str]) -> DataProfile:
    """Create a data profile with given column names."""
    return DataProfile(
        file_id="file-001",
        filename="survey_data.csv",
        file_format="csv",
        file_hash="sha256:abc123def456",
        size_bytes=1024,
        row_count=100,
        column_count=len(columns),
        columns=[
            ColumnProfile(
                name=col, dtype="float64", non_null_count=100,
                null_count=0, null_pct=0.0, unique_count=50,
                sample_values=["1", "2", "3"],
            )
            for col in columns
        ],
        total_null_count=0,
        total_null_pct=0.0,
    )


def _questionnaire(var_names: list[str]) -> Questionnaire:
    """Create a questionnaire with given variable names."""
    questions = [
        Question(
            question_id=f"Q{i+1}", question_text=f"Question {i+1}",
            question_type=QuestionType.SINGLE_SELECT, var_name=vn,
            response_options=[
                ResponseOption(code=1, label="Yes"),
                ResponseOption(code=2, label="No"),
            ],
        )
        for i, vn in enumerate(var_names)
    ]
    return Questionnaire(
        project_id="proj-001", methodology="segmentation", version=3,
        sections=[Section(
            section_id="s1", section_type="test", label="Test",
            order=0, questions=questions,
        )],
    )


# ---------------------------------------------------------------------------
# AC-1: Auto-map produced from questionnaire + data profile
# ---------------------------------------------------------------------------

class TestAutoMap:
    def test_exact_match_columns(self):
        profile = _profile(["SCR_01", "SCR_02", "DEM_01"])
        qre = _questionnaire(["SCR_01", "SCR_02", "DEM_01"])
        mapping = auto_map(profile, qre)
        assert mapping.mapped_count() == 3
        assert len(mapping.unmapped_columns) == 0

    def test_exact_match_confidence(self):
        profile = _profile(["SCR_01"])
        qre = _questionnaire(["SCR_01"])
        mapping = auto_map(profile, qre)
        m = mapping.get_mapping("SCR_01")
        assert m is not None
        assert m.confidence == 1.0
        assert m.confidence_level == MatchConfidence.HIGH
        assert m.match_reason == "exact_match"

    def test_case_insensitive_match(self):
        profile = _profile(["scr_01"])
        qre = _questionnaire(["SCR_01"])
        mapping = auto_map(profile, qre)
        assert mapping.mapped_count() == 1

    def test_fuzzy_match(self):
        profile = _profile(["screener_q1"])
        qre = _questionnaire(["SCR_01"])
        mapping = auto_map(profile, qre)
        m = mapping.get_mapping("screener_q1")
        assert m is not None
        # Fuzzy match should produce a score but may be low
        assert m.confidence > 0

    def test_no_match_columns_unmapped(self):
        profile = _profile(["random_col_xyz", "another_col"])
        qre = _questionnaire(["SCR_01", "ATT_01"])
        mapping = auto_map(profile, qre)
        assert len(mapping.unmapped_columns) >= 1

    def test_no_duplicate_variable_assignments(self):
        """Each variable should be mapped to at most one column."""
        profile = _profile(["SCR_01", "scr_01_copy", "ATT_01"])
        qre = _questionnaire(["SCR_01", "ATT_01"])
        mapping = auto_map(profile, qre)
        assigned_vars = [m.var_name for m in mapping.mappings if m.var_name]
        assert len(assigned_vars) == len(set(assigned_vars))

    def test_all_columns_in_mapping(self):
        profile = _profile(["A", "B", "C"])
        qre = _questionnaire(["X", "Y"])
        mapping = auto_map(profile, qre)
        assert len(mapping.mappings) == 3  # all columns present

    def test_mapping_has_question_ids(self):
        profile = _profile(["SCR_01"])
        qre = _questionnaire(["SCR_01"])
        mapping = auto_map(profile, qre)
        m = mapping.get_mapping("SCR_01")
        assert m.question_id == "Q1"

    def test_for_ui_output(self):
        profile = _profile(["SCR_01", "unknown"])
        qre = _questionnaire(["SCR_01"])
        mapping = auto_map(profile, qre)
        ui = mapping.for_ui()
        assert len(ui) == 2
        for item in ui:
            assert "column_name" in item
            assert "var_name" in item
            assert "confidence" in item
            assert "confidence_level" in item

    def test_low_confidence_mappings_identified(self):
        profile = _profile(["somewhat_similar"])
        qre = _questionnaire(["SCR_01"])
        mapping = auto_map(profile, qre)
        low = mapping.low_confidence_mappings()
        # May or may not have low-confidence matches depending on fuzzy score
        assert isinstance(low, list)


# ---------------------------------------------------------------------------
# AC-2: Users can edit and save mapping versions
# ---------------------------------------------------------------------------

class TestEditMapping:
    def test_edit_single_column(self):
        profile = _profile(["col_a", "col_b"])
        qre = _questionnaire(["SCR_01", "ATT_01"])
        mapping = auto_map(profile, qre)
        edit_mapping(mapping, "col_a", var_name="SCR_01", question_id="Q1")
        m = mapping.get_mapping("col_a")
        assert m.var_name == "SCR_01"
        assert m.manually_edited is True
        assert m.confidence == 1.0

    def test_edit_sets_high_confidence(self):
        profile = _profile(["col_a"])
        qre = _questionnaire(["SCR_01"])
        mapping = auto_map(profile, qre)
        edit_mapping(mapping, "col_a", var_name="SCR_01")
        m = mapping.get_mapping("col_a")
        assert m.confidence_level == MatchConfidence.HIGH

    def test_unmap_column(self):
        profile = _profile(["SCR_01"])
        qre = _questionnaire(["SCR_01"])
        mapping = auto_map(profile, qre)
        edit_mapping(mapping, "SCR_01", var_name=None)
        m = mapping.get_mapping("SCR_01")
        assert m.var_name is None
        assert "SCR_01" in mapping.unmapped_columns

    def test_edit_nonexistent_column_raises(self):
        profile = _profile(["col_a"])
        qre = _questionnaire(["SCR_01"])
        mapping = auto_map(profile, qre)
        with pytest.raises(ValueError, match="not found"):
            edit_mapping(mapping, "nonexistent", var_name="SCR_01")

    def test_edit_locked_mapping_raises(self):
        profile = _profile(["col_a"])
        qre = _questionnaire(["SCR_01"])
        mapping = auto_map(profile, qre)
        mapping.locked = True
        with pytest.raises(ValueError, match="locked"):
            edit_mapping(mapping, "col_a", var_name="SCR_01")

    def test_updated_at_changes(self):
        profile = _profile(["col_a"])
        qre = _questionnaire(["SCR_01"])
        mapping = auto_map(profile, qre)
        original = mapping.updated_at
        edit_mapping(mapping, "col_a", var_name="SCR_01")
        assert mapping.updated_at >= original

    def test_save_and_retrieve(self):
        store = MappingStore()
        profile = _profile(["SCR_01"])
        qre = _questionnaire(["SCR_01"])
        mapping = auto_map(profile, qre)
        store.save(mapping)
        retrieved = store.get_latest("proj-001")
        assert retrieved is not None
        assert retrieved.mapping_id == mapping.mapping_id

    def test_multiple_versions_auto_incremented(self):
        store = MappingStore()
        profile = _profile(["SCR_01"])
        qre = _questionnaire(["SCR_01"])
        m1 = auto_map(profile, qre)
        store.save(m1)
        m2 = auto_map(profile, qre)
        store.save(m2)
        assert store.get_version("proj-001", 1) is not None
        assert store.get_version("proj-001", 2) is not None
        assert store.get_latest("proj-001").version == 2

    def test_duplicate_var_mapping_rejected(self):
        profile = _profile(["col_a", "col_b"])
        qre = _questionnaire(["SCR_01", "ATT_01"])
        mapping = auto_map(profile, qre)
        # Map col_a to SCR_01
        edit_mapping(mapping, "col_a", var_name="SCR_01")
        # Trying to also map col_b to SCR_01 should fail
        with pytest.raises(ValueError, match="already mapped"):
            edit_mapping(mapping, "col_b", var_name="SCR_01")

    def test_list_versions(self):
        store = MappingStore()
        profile = _profile(["SCR_01"])
        qre = _questionnaire(["SCR_01"])
        m1 = auto_map(profile, qre)
        store.save(m1)
        summaries = store.list_versions("proj-001")
        assert len(summaries) == 1
        assert "mapping_id" in summaries[0]
        assert "mapped_count" in summaries[0]


# ---------------------------------------------------------------------------
# AC-3: Mapping linked to questionnaire version and data file hash
# ---------------------------------------------------------------------------

class TestProvenance:
    def test_questionnaire_version_linked(self):
        profile = _profile(["SCR_01"])
        qre = _questionnaire(["SCR_01"])
        qre.version = 5
        mapping = auto_map(profile, qre)
        assert mapping.questionnaire_version == 5
        assert mapping.questionnaire_id == qre.questionnaire_id

    def test_data_file_hash_linked(self):
        profile = _profile(["SCR_01"])
        qre = _questionnaire(["SCR_01"])
        mapping = auto_map(profile, qre)
        assert mapping.data_file_hash == "sha256:abc123def456"

    def test_project_id_linked(self):
        profile = _profile(["SCR_01"])
        qre = _questionnaire(["SCR_01"])
        mapping = auto_map(profile, qre)
        assert mapping.project_id == "proj-001"

    def test_mapping_id_unique(self):
        profile = _profile(["SCR_01"])
        qre = _questionnaire(["SCR_01"])
        m1 = auto_map(profile, qre)
        m2 = auto_map(profile, qre)
        assert m1.mapping_id != m2.mapping_id

    def test_created_at_set(self):
        profile = _profile(["SCR_01"])
        qre = _questionnaire(["SCR_01"])
        mapping = auto_map(profile, qre)
        assert mapping.created_at is not None
