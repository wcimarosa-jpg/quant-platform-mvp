"""Test scaffolding for P07-02: Drivers suite.

Tests will verify ridge regression, Pearson correlations, and
weighted-effects outputs against the DriversResultSummary schema.
Uses synthetic fixture data from data/fixtures/small/p07_synthetic.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make fixture importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from data.fixtures.small.p07_synthetic import make_survey_df, iv_columns, dv_columns
from packages.survey_analysis.result_schemas import DriversResultSummary, validate_result


class TestDriversFixture:
    """Verify synthetic fixture is usable for drivers tests."""

    def test_fixture_has_iv_columns(self):
        df = make_survey_df()
        for col in iv_columns():
            assert col in df.columns

    def test_fixture_has_dv_columns(self):
        df = make_survey_df()
        for col in dv_columns():
            assert col in df.columns

    def test_fixture_row_count(self):
        df = make_survey_df()
        assert len(df) == 200

    def test_schema_validates_sample(self):
        """Verify schema can validate a hand-built result dict."""
        sample = {
            "analysis_type": "drivers",
            "regressions": [{
                "dv_name": "SAT_01", "segment": "Total", "r_squared": 0.35,
                "n": 200, "coefficients": [
                    {"variable": "ATT_01", "coefficient": 0.42, "significant": True},
                ],
            }],
            "pearson_correlations": [{
                "iv": "ATT_01", "dv": "SAT_01", "r": 0.55, "p_value": 0.001, "n": 200,
            }],
            "weighted_effects": [{
                "variable": "ATT_01", "top_n_count": 5, "total_combos": 12, "frequency_pct": 41.7,
            }],
            "top_drivers": ["ATT_01"],
        }
        result = validate_result("drivers", sample)
        assert isinstance(result, DriversResultSummary)
