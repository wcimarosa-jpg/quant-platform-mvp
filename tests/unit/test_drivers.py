"""Tests for P07-02: Drivers suite (ridge + Pearson + weighted-effects).

Verifies real computation against synthetic fixture data.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from data.fixtures.small.p07_synthetic import make_survey_df, iv_columns, dv_columns
from packages.survey_analysis.drivers import (
    analysis_drivers,
    run_pearson,
    run_ridge,
    run_weighted_effects,
)
from packages.survey_analysis.result_schemas import DriversResultSummary, validate_result
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
# Ridge regression
# ---------------------------------------------------------------------------

class TestRidgeRegression:
    def test_ridge_produces_results(self):
        df = _df()
        results = run_ridge(df, iv_columns()[:5], "SAT_01")
        assert len(results) >= 1
        assert results[0]["dv_name"] == "SAT_01"
        assert results[0]["segment"] == "Total"

    def test_ridge_r_squared_in_range(self):
        df = _df()
        results = run_ridge(df, iv_columns()[:10], "SAT_01")
        for r in results:
            assert 0.0 <= r["r_squared"] <= 1.0

    def test_ridge_has_coefficients(self):
        df = _df()
        results = run_ridge(df, iv_columns()[:5], "SAT_01")
        assert len(results[0]["coefficients"]) == 5
        for c in results[0]["coefficients"]:
            assert "variable" in c
            assert "coefficient" in c

    def test_ridge_with_segments(self):
        df = _df()
        results = run_ridge(df, iv_columns()[:5], "SAT_01", segment_col="GENDER")
        segments = {r["segment"] for r in results}
        assert "Total" in segments
        assert len(segments) >= 2  # Total + at least one gender

    def test_ridge_n_matches_data(self):
        df = _df()
        results = run_ridge(df, iv_columns()[:5], "SAT_01")
        assert results[0]["n"] == 200

    def test_ridge_different_alpha(self):
        df = _df()
        r1 = run_ridge(df, iv_columns()[:5], "SAT_01", alpha=0.01)
        r2 = run_ridge(df, iv_columns()[:5], "SAT_01", alpha=10.0)
        # Higher alpha should shrink coefficients more
        max_coef_1 = max(abs(c["coefficient"]) for c in r1[0]["coefficients"])
        max_coef_2 = max(abs(c["coefficient"]) for c in r2[0]["coefficients"])
        assert max_coef_1 >= max_coef_2


# ---------------------------------------------------------------------------
# Pearson correlations
# ---------------------------------------------------------------------------

class TestPearson:
    def test_pearson_produces_results(self):
        df = _df()
        results = run_pearson(df, iv_columns()[:3], dv_columns()[:2])
        assert len(results) == 6  # 3 IVs x 2 DVs

    def test_pearson_r_in_range(self):
        df = _df()
        results = run_pearson(df, iv_columns()[:5], dv_columns())
        for r in results:
            assert -1.0 <= r["r"] <= 1.0
            assert 0.0 <= r["p_value"] <= 1.0
            assert r["n"] > 0

    def test_pearson_with_known_correlation(self):
        """Perfect correlation should produce r ≈ 1.0."""
        df = _df().copy()
        df["PERFECT_DV"] = df[iv_columns()[0]] * 2 + 1
        results = run_pearson(df, [iv_columns()[0]], ["PERFECT_DV"])
        assert abs(results[0]["r"] - 1.0) < 0.001


# ---------------------------------------------------------------------------
# Weighted-effects
# ---------------------------------------------------------------------------

class TestWeightedEffects:
    def test_weighted_effects_from_regressions(self):
        df = _df()
        regs = []
        for dv in dv_columns():
            regs.extend(run_ridge(df, iv_columns()[:10], dv))
        we = run_weighted_effects(regs, top_n=5)
        assert len(we) > 0
        assert we[0]["frequency_pct"] > 0

    def test_weighted_effects_sorted_descending(self):
        df = _df()
        regs = []
        for dv in dv_columns():
            regs.extend(run_ridge(df, iv_columns()[:10], dv))
        we = run_weighted_effects(regs, top_n=5)
        pcts = [w["frequency_pct"] for w in we]
        assert pcts == sorted(pcts, reverse=True)

    def test_weighted_effects_total_combos(self):
        df = _df()
        regs = run_ridge(df, iv_columns()[:5], "SAT_01")
        we = run_weighted_effects(regs, top_n=3)
        assert we[0]["total_combos"] == len(regs)


# ---------------------------------------------------------------------------
# Full suite via orchestrator
# ---------------------------------------------------------------------------

class TestDriversOrchestrator:
    def test_full_drivers_via_execute_run(self):
        df = _df()
        run = create_run("proj-001", RunConfig(analysis_type="drivers"), _versions())
        execute_run(run, df=df, iv_cols=iv_columns(), dv_cols=dv_columns())
        assert run.status.value == "completed"
        assert run.result_summary is not None
        assert "regressions" in run.result_summary
        assert "pearson_correlations" in run.result_summary
        assert "weighted_effects" in run.result_summary
        assert "top_drivers" in run.result_summary

    def test_result_validates_against_schema(self):
        df = _df()
        run = create_run("proj-001", RunConfig(analysis_type="drivers"), _versions())
        execute_run(run, df=df, iv_cols=iv_columns(), dv_cols=dv_columns())
        result = validate_result("drivers", run.result_summary)
        assert isinstance(result, DriversResultSummary)

    def test_missing_data_fails_with_actionable_error(self):
        run = create_run("proj-001", RunConfig(analysis_type="drivers"), _versions())
        execute_run(run, iv_cols=iv_columns(), dv_cols=dv_columns())
        assert run.status.value == "failed"
        assert "DataFrame" in run.error_message

    def test_missing_iv_cols_fails(self):
        df = _df()
        run = create_run("proj-001", RunConfig(analysis_type="drivers"), _versions())
        execute_run(run, df=df, dv_cols=dv_columns())
        assert run.status.value == "failed"
        assert "iv_cols" in run.error_message

    def test_bad_column_names_fail(self):
        df = _df()
        run = create_run("proj-001", RunConfig(analysis_type="drivers"), _versions())
        execute_run(run, df=df, iv_cols=["NONEXISTENT"], dv_cols=dv_columns())
        assert run.status.value == "failed"
        assert "NONEXISTENT" in run.error_message

    def test_with_segment_column(self):
        df = _df()
        run = create_run("proj-001", RunConfig(analysis_type="drivers"), _versions())
        execute_run(run, df=df, iv_cols=iv_columns()[:10], dv_cols=["SAT_01"], segment_col="GENDER")
        assert run.status.value == "completed"
        regs = run.result_summary["regressions"]
        segments = {r["segment"] for r in regs}
        assert "Total" in segments
        assert len(segments) >= 2
