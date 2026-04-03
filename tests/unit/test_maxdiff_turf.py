"""Test scaffolding for P07-04: MaxDiff + TURF suite.

Tests will verify count-based MaxDiff scoring and greedy TURF
against the MaxDiffTURFResultSummary schema.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from data.fixtures.small.p07_synthetic import (
    make_survey_df,
    maxdiff_items,
    turf_acceptance_columns,
)
from packages.survey_analysis.result_schemas import MaxDiffTURFResultSummary, validate_result


class TestMaxDiffTURFFixture:
    """Verify synthetic fixture is usable for MaxDiff+TURF tests."""

    def test_fixture_has_maxdiff_tasks(self):
        df = make_survey_df()
        for col in maxdiff_items():
            assert col in df.columns

    def test_fixture_has_turf_acceptance(self):
        df = make_survey_df()
        for col in turf_acceptance_columns():
            assert col in df.columns

    def test_maxdiff_values_are_valid(self):
        df = make_survey_df()
        for col in maxdiff_items():
            assert set(df[col].unique()).issubset({-1, 0, 1})

    def test_turf_values_are_binary(self):
        df = make_survey_df()
        for col in turf_acceptance_columns():
            assert set(df[col].unique()).issubset({0, 1})

    def test_schema_validates_sample(self):
        sample = {
            "analysis_type": "maxdiff_turf",
            "total_respondents": 200,
            "item_scores": [{
                "item": "Item A", "best_count": 40, "worst_count": 10,
                "best_worst_diff": 30, "rescaled_score": 85.0,
            }],
            "item_ranking": ["Item A"],
            "turf_portfolios": [{
                "portfolio_size": 1, "items": ["Item A"],
                "reach_count": 120, "reach_pct": 60.0, "avg_frequency": 1.0,
            }],
            "optimal_portfolio": {
                "portfolio_size": 3, "items": ["Item A", "Item B", "Item C"],
                "reach_count": 180, "reach_pct": 90.0, "avg_frequency": 1.8,
            },
        }
        result = validate_result("maxdiff_turf", sample)
        assert isinstance(result, MaxDiffTURFResultSummary)
        assert result.total_respondents == 200
