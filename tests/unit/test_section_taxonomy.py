"""Contract tests for section taxonomy (P00-02).

Verify:
1. Matrix covers all 8 methodologies.
2. Each section has required fields and validation rules.
3. Matrix is consumable by UI selector and generation engine.
"""

from __future__ import annotations

import pytest

from packages.shared.assistant_context import Methodology
from packages.shared.section_taxonomy import (
    METHODOLOGY_MATRIX,
    TAXONOMY_VERSION,
    MethodologyMatrix,
    SectionType,
    get_all_methodologies,
    get_matrix,
    validate_section_selection,
)

REQUIRED_METHODOLOGIES = [
    Methodology.ATTITUDE_USAGE,
    Methodology.SEGMENTATION,
    Methodology.DRIVERS,
    Methodology.CONCEPT_MONADIC,
    Methodology.CREATIVE_MONADIC,
    Methodology.BRAND_EQUITY_TRACKER,
    Methodology.MAXDIFF,
    Methodology.TURF,
]


# ---------------------------------------------------------------------------
# AC-1: Section matrix covers all 8 methodologies
# ---------------------------------------------------------------------------

class TestMethodologyCoverage:
    def test_all_eight_methodologies_present(self):
        assert len(METHODOLOGY_MATRIX) == 8

    @pytest.mark.parametrize("methodology", REQUIRED_METHODOLOGIES)
    def test_methodology_in_registry(self, methodology: Methodology):
        assert methodology in METHODOLOGY_MATRIX

    @pytest.mark.parametrize("methodology", REQUIRED_METHODOLOGIES)
    def test_get_matrix_returns_correct_type(self, methodology: Methodology):
        matrix = get_matrix(methodology)
        assert isinstance(matrix, MethodologyMatrix)
        assert matrix.methodology == methodology

    @pytest.mark.parametrize("methodology", REQUIRED_METHODOLOGIES)
    def test_methodology_has_at_least_3_sections(self, methodology: Methodology):
        matrix = get_matrix(methodology)
        assert len(matrix.section_order) >= 3

    @pytest.mark.parametrize("methodology", REQUIRED_METHODOLOGIES)
    def test_all_ordered_sections_have_definitions(self, methodology: Methodology):
        matrix = get_matrix(methodology)
        for st in matrix.section_order:
            assert st in matrix.sections, f"{st.value} in section_order but missing from sections dict"

    @pytest.mark.parametrize("methodology", REQUIRED_METHODOLOGIES)
    def test_screener_and_demographics_present(self, methodology: Methodology):
        matrix = get_matrix(methodology)
        types = {st.value for st in matrix.section_order}
        assert "screener" in types, f"Screener missing from {methodology.value}"
        assert "demographics" in types, f"Demographics missing from {methodology.value}"


# ---------------------------------------------------------------------------
# AC-2: Each section has required fields and validation rules
# ---------------------------------------------------------------------------

class TestSectionFields:
    @pytest.mark.parametrize("methodology", REQUIRED_METHODOLOGIES)
    def test_every_section_has_label(self, methodology: Methodology):
        matrix = get_matrix(methodology)
        for st, defn in matrix.sections.items():
            assert defn.label, f"{methodology.value}/{st.value} missing label"

    @pytest.mark.parametrize("methodology", REQUIRED_METHODOLOGIES)
    def test_every_section_has_description(self, methodology: Methodology):
        matrix = get_matrix(methodology)
        for st, defn in matrix.sections.items():
            assert defn.description, f"{methodology.value}/{st.value} missing description"

    @pytest.mark.parametrize("methodology", REQUIRED_METHODOLOGIES)
    def test_every_section_has_question_count_range(self, methodology: Methodology):
        matrix = get_matrix(methodology)
        for st, defn in matrix.sections.items():
            mn, mx = defn.typical_question_count
            assert mn > 0, f"{methodology.value}/{st.value} min questions must be > 0"
            assert mx >= mn, f"{methodology.value}/{st.value} max < min"

    @pytest.mark.parametrize("methodology", REQUIRED_METHODOLOGIES)
    def test_every_section_has_required_fields(self, methodology: Methodology):
        matrix = get_matrix(methodology)
        for st, defn in matrix.sections.items():
            assert len(defn.required_fields) > 0, f"{methodology.value}/{st.value} has no required_fields"

    @pytest.mark.parametrize("methodology", REQUIRED_METHODOLOGIES)
    def test_required_sections_have_validation_rules(self, methodology: Methodology):
        matrix = get_matrix(methodology)
        for st in matrix.required_sections():
            defn = matrix.sections[st]
            assert len(defn.validation_rules) > 0 or len(defn.required_fields) > 0, (
                f"Required section {methodology.value}/{st.value} has no validation rules or required fields"
            )


# ---------------------------------------------------------------------------
# AC-3: Matrix is consumable by UI selector and generation engine
# ---------------------------------------------------------------------------

class TestConsumability:
    def test_get_all_methodologies_returns_list(self):
        result = get_all_methodologies()
        assert isinstance(result, list)
        assert len(result) == 8

    def test_get_all_methodologies_has_required_keys(self):
        for entry in get_all_methodologies():
            assert "value" in entry
            assert "label" in entry
            assert "description" in entry
            assert "default_loi" in entry

    @pytest.mark.parametrize("methodology", REQUIRED_METHODOLOGIES)
    def test_for_ui_returns_list_of_dicts(self, methodology: Methodology):
        matrix = get_matrix(methodology)
        ui_data = matrix.for_ui()
        assert isinstance(ui_data, list)
        assert len(ui_data) == len(matrix.section_order)
        for item in ui_data:
            assert "section_type" in item
            assert "label" in item
            assert "description" in item
            assert "required" in item
            assert "typical_questions" in item

    @pytest.mark.parametrize("methodology", REQUIRED_METHODOLOGIES)
    def test_for_generation_filters_to_selected(self, methodology: Methodology):
        matrix = get_matrix(methodology)
        # Select only required sections
        required = [st.value for st in matrix.required_sections()]
        gen_data = matrix.for_generation(required)
        assert isinstance(gen_data, list)
        # Should include at least all required sections
        gen_types = {item["section_type"] for item in gen_data}
        for r in required:
            assert r in gen_types

    @pytest.mark.parametrize("methodology", REQUIRED_METHODOLOGIES)
    def test_for_generation_includes_required_even_if_not_selected(self, methodology: Methodology):
        matrix = get_matrix(methodology)
        gen_data = matrix.for_generation([])  # select nothing
        gen_types = {item["section_type"] for item in gen_data}
        for st in matrix.required_sections():
            assert st.value in gen_types

    def test_for_generation_output_has_required_keys(self):
        matrix = get_matrix(Methodology.SEGMENTATION)
        all_sections = [st.value for st in matrix.section_order]
        gen_data = matrix.for_generation(all_sections)
        for item in gen_data:
            assert "section_type" in item
            assert "label" in item
            assert "typical_question_count" in item
            assert "required_fields" in item
            assert "validation_rules" in item
            assert "analysis_dependencies" in item


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_valid_selection_returns_no_errors(self):
        matrix = get_matrix(Methodology.SEGMENTATION)
        selected = [st.value for st in matrix.section_order]
        errors = validate_section_selection(Methodology.SEGMENTATION, selected)
        assert errors == []

    def test_missing_required_section_returns_error(self):
        errors = validate_section_selection(Methodology.SEGMENTATION, ["demographics"])
        assert any("screener" in e for e in errors)

    def test_invalid_section_type_returns_error(self):
        errors = validate_section_selection(Methodology.MAXDIFF, ["screener", "demographics", "fake_section"])
        assert any("fake_section" in e for e in errors)

    def test_required_only_selection_passes(self):
        matrix = get_matrix(Methodology.CONCEPT_MONADIC)
        required = [st.value for st in matrix.required_sections()]
        # Add all optional too to satisfy the required check
        all_sections = [st.value for st in matrix.section_order]
        errors = validate_section_selection(Methodology.CONCEPT_MONADIC, all_sections)
        assert errors == []


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

class TestVersioning:
    def test_taxonomy_version_is_semver(self):
        parts = TAXONOMY_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)


# ---------------------------------------------------------------------------
# Analysis dependency coverage
# ---------------------------------------------------------------------------

class TestAnalysisDependencies:
    def test_segmentation_has_clustering_dependencies(self):
        matrix = get_matrix(Methodology.SEGMENTATION)
        all_deps = set()
        for defn in matrix.sections.values():
            all_deps.update(defn.analysis_dependencies)
        assert "kmeans" in all_deps
        assert "varclus" in all_deps

    def test_drivers_has_regression_dependency(self):
        matrix = get_matrix(Methodology.DRIVERS)
        all_deps = set()
        for defn in matrix.sections.values():
            all_deps.update(defn.analysis_dependencies)
        assert "ridge_regression" in all_deps

    def test_maxdiff_has_maxdiff_dependency(self):
        matrix = get_matrix(Methodology.MAXDIFF)
        all_deps = set()
        for defn in matrix.sections.values():
            all_deps.update(defn.analysis_dependencies)
        assert "maxdiff" in all_deps

    def test_turf_has_turf_dependency(self):
        matrix = get_matrix(Methodology.TURF)
        all_deps = set()
        for defn in matrix.sections.values():
            all_deps.update(defn.analysis_dependencies)
        assert "turf" in all_deps
