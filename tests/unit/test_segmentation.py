"""Tests for P07-03: Segmentation suite (VarClus + KMeans + profiles).

Verifies real computation against synthetic fixture data.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from data.fixtures.small.p07_synthetic import make_survey_df, iv_columns
from packages.survey_analysis.segmentation import (
    build_profiles,
    run_kmeans,
    run_varclus,
)
from packages.survey_analysis.result_schemas import SegmentationResultSummary, validate_result
from packages.survey_analysis.run_orchestrator import (
    AnalysisError,
    AnalysisRun,
    RunConfig,
    RunVersions,
    create_run,
    execute_run,
)


def _df():
    return make_survey_df(n=200, seed=42)


def _versions():
    return RunVersions(
        questionnaire_id="qre-001", questionnaire_version=1,
        mapping_id="map-001", mapping_version=1, data_file_hash="sha256:test",
    )


# ---------------------------------------------------------------------------
# VarClus
# ---------------------------------------------------------------------------

class TestVarClus:
    def test_varclus_produces_clusters(self):
        clusters = run_varclus(_df(), iv_columns())
        assert len(clusters) >= 2

    def test_each_cluster_has_representative(self):
        for c in run_varclus(_df(), iv_columns()):
            assert c["representative"] in c["variables"]

    def test_all_variables_assigned(self):
        all_vars = [v for c in run_varclus(_df(), iv_columns()) for v in c["variables"]]
        assert set(all_vars) == set(iv_columns())

    def test_no_duplicate_assignments(self):
        all_vars = [v for c in run_varclus(_df(), iv_columns()) for v in c["variables"]]
        assert len(all_vars) == len(set(all_vars))

    def test_higher_max_eigen_fewer_clusters(self):
        c1 = run_varclus(_df(), iv_columns(), max_eigen=0.3)
        c2 = run_varclus(_df(), iv_columns(), max_eigen=1.0)
        assert len(c1) >= len(c2)

    def test_missing_columns_raises(self):
        with pytest.raises(AnalysisError, match="not found"):
            run_varclus(_df(), ["NONEXISTENT"])


# ---------------------------------------------------------------------------
# KMeans
# ---------------------------------------------------------------------------

class TestKMeans:
    def test_kmeans_produces_clusters(self):
        result = run_kmeans(_df(), iv_columns()[:10])
        assert result["selected_k"] >= 2
        assert len(result["kmeans_clusters"]) == result["selected_k"]

    def test_silhouette_in_range(self):
        assert -1.0 <= run_kmeans(_df(), iv_columns()[:10])["silhouette_score"] <= 1.0

    def test_cluster_sizes_sum(self):
        result = run_kmeans(_df(), iv_columns()[:10])
        total = sum(c["size"] for c in result["kmeans_clusters"])
        assert total > 100

    def test_cluster_has_centroid(self):
        for c in run_kmeans(_df(), iv_columns()[:5])["kmeans_clusters"]:
            assert len(c["centroid"]) == 5

    def test_deterministic(self):
        r1 = run_kmeans(_df(), iv_columns()[:10], random_state=42)
        r2 = run_kmeans(_df(), iv_columns()[:10], random_state=42)
        assert r1["selected_k"] == r2["selected_k"]

    def test_custom_k_values(self):
        assert run_kmeans(_df(), iv_columns()[:10], k_values=[2, 3])["selected_k"] in [2, 3]

    def test_missing_columns_raises(self):
        with pytest.raises(AnalysisError):
            run_kmeans(_df(), ["NONEXISTENT"])


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

class TestProfiles:
    def test_profiles_built(self):
        km = run_kmeans(_df(), iv_columns()[:10])
        profiles = build_profiles(_df(), km["cluster_assignments"], km["row_index"], ["GENDER", "AGE_GROUP"])
        assert len(profiles) == 2

    def test_profile_values_per_segment(self):
        km = run_kmeans(_df(), iv_columns()[:10])
        profiles = build_profiles(_df(), km["cluster_assignments"], km["row_index"], ["GENDER"])
        assert len(profiles[0]["values"]) == km["selected_k"]

    def test_empty_profile_vars(self):
        km = run_kmeans(_df(), iv_columns()[:10])
        assert build_profiles(_df(), km["cluster_assignments"], km["row_index"], []) == []


# ---------------------------------------------------------------------------
# Composite orchestrator
# ---------------------------------------------------------------------------

class TestSegmentationOrchestrator:
    def test_composite_run_completes(self):
        import packages.survey_analysis.segmentation  # noqa: F401
        run = create_run("proj-001", RunConfig(analysis_type="segmentation"), _versions())
        execute_run(run, df=_df(), clustering_vars=iv_columns(), profile_vars=["GENDER", "AGE_GROUP"])
        assert run.status.value == "completed"

    def test_result_has_all_fields(self):
        import packages.survey_analysis.segmentation  # noqa: F401
        run = create_run("proj-001", RunConfig(analysis_type="segmentation"), _versions())
        execute_run(run, df=_df(), clustering_vars=iv_columns(), profile_vars=["GENDER"])
        rs = run.result_summary
        assert "varclus_clusters" in rs
        assert "kmeans_clusters" in rs
        assert "selected_k" in rs
        assert "silhouette_score" in rs
        assert "profile_tables" in rs

    def test_result_validates_against_schema(self):
        import packages.survey_analysis.segmentation  # noqa: F401
        run = create_run("proj-001", RunConfig(analysis_type="segmentation"), _versions())
        execute_run(run, df=_df(), clustering_vars=iv_columns(), profile_vars=["GENDER"])
        result = validate_result("segmentation", run.result_summary)
        assert isinstance(result, SegmentationResultSummary)

    def test_missing_data_fails(self):
        import packages.survey_analysis.segmentation  # noqa: F401
        run = create_run("proj-001", RunConfig(analysis_type="segmentation"), _versions())
        execute_run(run, clustering_vars=iv_columns())
        assert run.status.value == "failed"
