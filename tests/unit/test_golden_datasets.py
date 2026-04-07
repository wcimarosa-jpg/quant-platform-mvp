"""Tests for P10-03: Golden datasets and expected outputs per methodology.

AC-1: Golden fixtures exist for all registered methodologies.
AC-2: Regression tests compare current output against expected tolerances.
AC-3: Fixture update workflow is documented (generator.py docstring).
"""

from __future__ import annotations

import json
from math import isclose
from pathlib import Path

import pytest

# Import analyses to trigger registration
import packages.survey_analysis.drivers  # noqa: F401
import packages.survey_analysis.segmentation  # noqa: F401
import packages.survey_analysis.maxdiff_turf  # noqa: F401

from data.fixtures.small.p07_synthetic import (
    dv_columns,
    iv_columns,
    make_survey_df,
    maxdiff_items,
    turf_acceptance_columns,
)
from packages.survey_analysis.run_orchestrator import (
    AnalysisRun,
    RunConfig,
    RunVersions,
    execute_run,
)
from packages.survey_analysis.result_schemas import (
    DriversResultSummary,
    MaxDiffTURFResultSummary,
    SegmentationResultSummary,
    validate_result,
)

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "golden"
SEED = 42
N = 200

# Tolerance for floating-point comparisons
ABS_TOL = 1e-6
REL_TOL = 1e-4


def _load_golden(name: str) -> dict:
    path = GOLDEN_DIR / f"{name}_expected.json"
    assert path.is_file(), f"Golden file not found: {path}"
    with open(path) as f:
        return json.load(f)


def _versions() -> RunVersions:
    return RunVersions(
        questionnaire_id="qre-golden",
        questionnaire_version=1,
        mapping_id="map-golden",
        mapping_version=1,
        data_file_hash="sha256:golden-fixture",
    )


def _run_analysis(analysis_type: str, **kwargs) -> dict:
    run = AnalysisRun(
        project_id="golden-test",
        config=RunConfig(analysis_type=analysis_type),
        versions=_versions(),
    )
    result = execute_run(run, **kwargs)
    assert result.status.value == "completed", f"{analysis_type} failed: {result.error_message}"
    return result.result_summary


def _approx(actual: float, expected: float) -> bool:
    """Check if actual is within tolerance of expected using math.isclose."""
    return isclose(actual, expected, rel_tol=REL_TOL, abs_tol=ABS_TOL)


# ---------------------------------------------------------------------------
# AC-1: Golden fixtures exist
# ---------------------------------------------------------------------------

class TestGoldenFixturesExist:
    def test_drivers_golden_exists(self):
        assert (GOLDEN_DIR / "drivers_expected.json").is_file()

    def test_maxdiff_turf_golden_exists(self):
        assert (GOLDEN_DIR / "maxdiff_turf_expected.json").is_file()

    def test_segmentation_golden_exists(self):
        assert (GOLDEN_DIR / "segmentation_expected.json").is_file()

    def test_generator_exists(self):
        assert (GOLDEN_DIR / "generator.py").is_file()

    def test_golden_files_are_valid_json(self):
        for name in ["drivers", "maxdiff_turf", "segmentation"]:
            data = _load_golden(name)
            assert isinstance(data, dict)
            assert "analysis_type" in data

    def test_golden_files_validate_against_schemas(self):
        for name, schema in [
            ("drivers", DriversResultSummary),
            ("maxdiff_turf", MaxDiffTURFResultSummary),
            ("segmentation", SegmentationResultSummary),
        ]:
            data = _load_golden(name)
            validated = schema.model_validate(data)
            assert validated.analysis_type == name


# ---------------------------------------------------------------------------
# AC-2: Regression tests — drivers
# ---------------------------------------------------------------------------

class TestDriversRegression:
    @pytest.fixture(autouse=True, scope="class")
    def setup(self, request):
        df = make_survey_df(n=N, seed=SEED)
        request.cls.golden = _load_golden("drivers")
        request.cls.actual = _run_analysis(
            "drivers", df=df, iv_cols=iv_columns(), dv_cols=dv_columns(),
        )

    def test_analysis_type_matches(self):
        assert self.actual["analysis_type"] == self.golden["analysis_type"]

    def test_regression_count_matches(self):
        assert len(self.actual["regressions"]) == len(self.golden["regressions"])

    def test_r_squared_within_tolerance(self):
        for act, exp in zip(self.actual["regressions"], self.golden["regressions"]):
            assert _approx(act["r_squared"], exp["r_squared"]), \
                f"R² mismatch for {act['dv_name']}/{act['segment']}: {act['r_squared']} vs {exp['r_squared']}"

    def test_coefficient_values_within_tolerance(self):
        for act_reg, exp_reg in zip(self.actual["regressions"], self.golden["regressions"]):
            for act_c, exp_c in zip(act_reg["coefficients"], exp_reg["coefficients"]):
                assert act_c["variable"] == exp_c["variable"]
                assert _approx(act_c["coefficient"], exp_c["coefficient"]), \
                    f"Coeff mismatch for {act_c['variable']}: {act_c['coefficient']} vs {exp_c['coefficient']}"

    def test_pearson_correlations_within_tolerance(self):
        for act, exp in zip(self.actual["pearson_correlations"], self.golden["pearson_correlations"]):
            assert act["iv"] == exp["iv"]
            assert act["dv"] == exp["dv"]
            assert _approx(act["r"], exp["r"]), \
                f"Pearson r mismatch {act['iv']}/{act['dv']}: {act['r']} vs {exp['r']}"

    def test_top_drivers_match(self):
        assert self.actual["top_drivers"] == self.golden["top_drivers"]

    def test_weighted_effects_match(self):
        for act, exp in zip(self.actual["weighted_effects"], self.golden["weighted_effects"]):
            assert act["variable"] == exp["variable"]
            assert act["top_n_count"] == exp["top_n_count"]


# ---------------------------------------------------------------------------
# AC-2: Regression tests — MaxDiff/TURF
# ---------------------------------------------------------------------------

class TestMaxDiffTURFRegression:
    @pytest.fixture(autouse=True, scope="class")
    def setup(self, request):
        df = make_survey_df(n=N, seed=SEED)
        request.cls.golden = _load_golden("maxdiff_turf")
        request.cls.actual = _run_analysis(
            "maxdiff_turf", df=df,
            maxdiff_columns=maxdiff_items(),
            acceptance_columns=turf_acceptance_columns(),
        )

    def test_total_respondents_match(self):
        assert self.actual["total_respondents"] == self.golden["total_respondents"]

    def test_item_ranking_match(self):
        assert self.actual["item_ranking"] == self.golden["item_ranking"]

    def test_item_scores_within_tolerance(self):
        for act, exp in zip(self.actual["item_scores"], self.golden["item_scores"]):
            assert act["item"] == exp["item"]
            assert act["best_count"] == exp["best_count"]
            assert act["worst_count"] == exp["worst_count"]
            assert _approx(act["rescaled_score"], exp["rescaled_score"])

    def test_turf_portfolios_match(self):
        assert len(self.actual["turf_portfolios"]) == len(self.golden["turf_portfolios"])
        for act, exp in zip(self.actual["turf_portfolios"], self.golden["turf_portfolios"]):
            assert act["portfolio_size"] == exp["portfolio_size"]
            assert act["items"] == exp["items"]
            assert act["reach_count"] == exp["reach_count"]
            assert _approx(act["reach_pct"], exp["reach_pct"])

    def test_optimal_portfolio_match(self):
        if self.golden.get("optimal_portfolio"):
            assert self.actual["optimal_portfolio"] is not None
            assert self.actual["optimal_portfolio"]["items"] == self.golden["optimal_portfolio"]["items"]


# ---------------------------------------------------------------------------
# AC-2: Regression tests — Segmentation
# ---------------------------------------------------------------------------

class TestSegmentationRegression:
    @pytest.fixture(autouse=True, scope="class")
    def setup(self, request):
        df = make_survey_df(n=N, seed=SEED)
        request.cls.golden = _load_golden("segmentation")
        request.cls.actual = _run_analysis(
            "segmentation", df=df, clustering_vars=iv_columns(),
        )

    def test_analysis_type_matches(self):
        assert self.actual["analysis_type"] == self.golden["analysis_type"]

    def test_selected_k_matches(self):
        assert self.actual["selected_k"] == self.golden["selected_k"]

    def test_silhouette_score_within_tolerance(self):
        assert _approx(self.actual["silhouette_score"], self.golden["silhouette_score"])

    def test_varclus_cluster_count_matches(self):
        assert len(self.actual["varclus_clusters"]) == len(self.golden["varclus_clusters"])

    def test_varclus_variables_match(self):
        for act, exp in zip(self.actual["varclus_clusters"], self.golden["varclus_clusters"]):
            assert set(act["variables"]) == set(exp["variables"])
            assert act["representative"] == exp["representative"]

    def test_kmeans_cluster_count_matches(self):
        assert len(self.actual["kmeans_clusters"]) == len(self.golden["kmeans_clusters"])

    def test_kmeans_cluster_sizes_match(self):
        act_sizes = sorted([c["size"] for c in self.actual["kmeans_clusters"]])
        exp_sizes = sorted([c["size"] for c in self.golden["kmeans_clusters"]])
        assert act_sizes == exp_sizes

    def test_kmeans_centroid_values_within_tolerance(self):
        """Centroid coordinates should be stable across runs."""
        # Match clusters by size to handle label permutation
        act_sorted = sorted(self.actual["kmeans_clusters"], key=lambda c: c["size"])
        exp_sorted = sorted(self.golden["kmeans_clusters"], key=lambda c: c["size"])
        for act, exp in zip(act_sorted, exp_sorted):
            assert act["size"] == exp["size"]
            for var in exp["centroid"]:
                assert var in act["centroid"], f"Missing centroid var: {var}"
                assert _approx(act["centroid"][var], exp["centroid"][var]), \
                    f"Centroid drift for cluster size={act['size']}, var={var}: " \
                    f"{act['centroid'][var]} vs {exp['centroid'][var]}"

    def test_profile_table_count_matches(self):
        assert len(self.actual["profile_tables"]) == len(self.golden["profile_tables"])
