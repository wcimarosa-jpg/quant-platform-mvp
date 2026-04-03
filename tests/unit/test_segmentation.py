"""Test scaffolding for P07-03: Segmentation suite.

Tests will verify VarClus, KMeans, and profile outputs against
the SegmentationResultSummary schema. Uses register_composite()
for the VarClus→KMeans pipeline.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from data.fixtures.small.p07_synthetic import make_survey_df, iv_columns
from packages.survey_analysis.result_schemas import SegmentationResultSummary, validate_result


class TestSegmentationFixture:
    """Verify synthetic fixture is usable for segmentation tests."""

    def test_fixture_has_clustering_variables(self):
        df = make_survey_df()
        for col in iv_columns():
            assert col in df.columns

    def test_fixture_has_enough_items_for_clustering(self):
        assert len(iv_columns()) >= 15

    def test_schema_validates_sample(self):
        sample = {
            "analysis_type": "segmentation",
            "varclus_clusters": [{
                "cluster_id": 1, "variables": ["ATT_01", "ATT_02"],
                "representative": "ATT_01", "eigenvalue": 2.1, "variance_explained": 0.42,
            }],
            "selected_k": 4,
            "silhouette_score": 0.35,
            "kmeans_clusters": [{
                "cluster_id": 1, "label": "Segment 1", "size": 50, "size_pct": 25.0,
                "centroid": {"ATT_01": 3.5, "ATT_02": 4.1},
            }],
            "profile_tables": [{
                "variable": "GENDER", "values": {"Segment 1": 55.0, "Segment 2": 48.0},
            }],
        }
        result = validate_result("segmentation", sample)
        assert isinstance(result, SegmentationResultSummary)
