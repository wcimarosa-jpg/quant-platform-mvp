"""Tests for P07-04: MaxDiff count-based scoring + TURF greedy reach.

Verifies real computation against synthetic fixture data.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from data.fixtures.small.p07_synthetic import (
    make_survey_df,
    maxdiff_items,
    turf_acceptance_columns,
)
from packages.survey_analysis.maxdiff_turf import (
    analysis_maxdiff_turf,
    run_turf,
    score_maxdiff,
)
from packages.survey_analysis.result_schemas import MaxDiffTURFResultSummary, validate_result
from packages.survey_analysis.run_orchestrator import (
    AnalysisError,
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
# MaxDiff scoring
# ---------------------------------------------------------------------------

class TestMaxDiffScoring:
    def test_produces_scores(self):
        scores = score_maxdiff(_df(), maxdiff_items())
        assert len(scores) == 12

    def test_scores_sorted_descending(self):
        scores = score_maxdiff(_df(), maxdiff_items())
        rescaled = [s["rescaled_score"] for s in scores]
        assert rescaled == sorted(rescaled, reverse=True)

    def test_rescaled_range_0_to_100(self):
        scores = score_maxdiff(_df(), maxdiff_items())
        for s in scores:
            assert 0.0 <= s["rescaled_score"] <= 100.0

    def test_best_worst_counts_are_data_driven(self):
        df = _df()
        scores = score_maxdiff(df, maxdiff_items())
        col = maxdiff_items()[0]
        expected_best = int((df[col] == 1).sum())
        expected_worst = int((df[col] == -1).sum())
        # Find the matching score (item label = column name by default)
        s = next(sc for sc in scores if sc["item"] == col)
        assert s["best_count"] == expected_best
        assert s["worst_count"] == expected_worst

    def test_best_worst_diff_correct(self):
        scores = score_maxdiff(_df(), maxdiff_items())
        for s in scores:
            assert s["best_worst_diff"] == s["best_count"] - s["worst_count"]

    def test_custom_labels(self):
        labels = {maxdiff_items()[0]: "Feature Alpha"}
        scores = score_maxdiff(_df(), maxdiff_items(), item_labels=labels)
        names = [s["item"] for s in scores]
        assert "Feature Alpha" in names

    def test_missing_columns_raises(self):
        with pytest.raises(AnalysisError, match="not found"):
            score_maxdiff(_df(), ["NONEXISTENT"])

    def test_known_winner(self):
        """Item with all best=1 should score 100."""
        df = pd.DataFrame({
            "A": [1] * 100,
            "B": [-1] * 100,
        })
        scores = score_maxdiff(df, ["A", "B"])
        a_score = next(s for s in scores if s["item"] == "A")
        b_score = next(s for s in scores if s["item"] == "B")
        assert a_score["rescaled_score"] == 100.0
        assert b_score["rescaled_score"] == 0.0


# ---------------------------------------------------------------------------
# TURF
# ---------------------------------------------------------------------------

class TestTURF:
    def test_produces_portfolios(self):
        portfolios = run_turf(_df(), turf_acceptance_columns())
        assert len(portfolios) >= 1

    def test_reach_increases_with_portfolio_size(self):
        portfolios = run_turf(_df(), turf_acceptance_columns())
        reaches = [p["reach_count"] for p in portfolios]
        for i in range(1, len(reaches)):
            assert reaches[i] >= reaches[i - 1]

    def test_reach_pct_in_range(self):
        portfolios = run_turf(_df(), turf_acceptance_columns())
        for p in portfolios:
            assert 0.0 <= p["reach_pct"] <= 100.0

    def test_portfolio_items_unique(self):
        portfolios = run_turf(_df(), turf_acceptance_columns())
        for p in portfolios:
            assert len(p["items"]) == len(set(p["items"]))

    def test_avg_frequency_positive(self):
        portfolios = run_turf(_df(), turf_acceptance_columns())
        for p in portfolios:
            if p["reach_count"] > 0:
                assert p["avg_frequency"] > 0

    def test_single_item_portfolio(self):
        portfolios = run_turf(_df(), turf_acceptance_columns(), portfolio_sizes=[1])
        assert len(portfolios) == 1
        assert portfolios[0]["portfolio_size"] == 1
        assert len(portfolios[0]["items"]) == 1

    def test_custom_portfolio_sizes(self):
        portfolios = run_turf(_df(), turf_acceptance_columns(), portfolio_sizes=[2, 4])
        sizes = [p["portfolio_size"] for p in portfolios]
        assert 2 in sizes
        assert 4 in sizes

    def test_deterministic(self):
        r1 = run_turf(_df(), turf_acceptance_columns())
        r2 = run_turf(_df(), turf_acceptance_columns())
        assert r1 == r2

    def test_missing_columns_raises(self):
        with pytest.raises(AnalysisError, match="not found"):
            run_turf(_df(), ["NONEXISTENT"])

    def test_known_reach(self):
        """All respondents accept item A → reach should be 100%."""
        df = pd.DataFrame({
            "A": [1] * 50,
            "B": [0] * 25 + [1] * 25,
        })
        portfolios = run_turf(df, ["A", "B"], portfolio_sizes=[1])
        assert portfolios[0]["items"] == ["A"]
        assert portfolios[0]["reach_pct"] == 100.0

    def test_tie_breaking_alphabetical(self):
        """When two items have identical reach, alphabetical wins."""
        df = pd.DataFrame({
            "B_item": [1, 0, 1, 0],
            "A_item": [1, 0, 1, 0],
        })
        portfolios = run_turf(df, ["B_item", "A_item"], portfolio_sizes=[1])
        # Both have same reach; A_item is alphabetically first
        assert portfolios[0]["items"] == ["A_item"]


# ---------------------------------------------------------------------------
# Full suite via orchestrator
# ---------------------------------------------------------------------------

class TestMaxDiffTURFOrchestrator:
    def test_full_run_completes(self):
        import packages.survey_analysis.maxdiff_turf  # noqa: F401
        run = create_run("proj-001", RunConfig(analysis_type="maxdiff_turf"), _versions())
        execute_run(
            run, df=_df(),
            maxdiff_columns=maxdiff_items(),
            acceptance_columns=turf_acceptance_columns(),
        )
        assert run.status.value == "completed"
        assert run.result_summary is not None

    def test_result_has_all_fields(self):
        import packages.survey_analysis.maxdiff_turf  # noqa: F401
        run = create_run("proj-001", RunConfig(analysis_type="maxdiff_turf"), _versions())
        execute_run(run, df=_df(), maxdiff_columns=maxdiff_items(), acceptance_columns=turf_acceptance_columns())
        rs = run.result_summary
        assert "item_scores" in rs
        assert "item_ranking" in rs
        assert "turf_portfolios" in rs
        assert "total_respondents" in rs
        assert rs["total_respondents"] == 200

    def test_result_validates_against_schema(self):
        import packages.survey_analysis.maxdiff_turf  # noqa: F401
        run = create_run("proj-001", RunConfig(analysis_type="maxdiff_turf"), _versions())
        execute_run(run, df=_df(), maxdiff_columns=maxdiff_items(), acceptance_columns=turf_acceptance_columns())
        result = validate_result("maxdiff_turf", run.result_summary)
        assert isinstance(result, MaxDiffTURFResultSummary)
        assert result.total_respondents == 200

    def test_missing_data_fails(self):
        import packages.survey_analysis.maxdiff_turf  # noqa: F401
        run = create_run("proj-001", RunConfig(analysis_type="maxdiff_turf"), _versions())
        execute_run(run, maxdiff_columns=maxdiff_items(), acceptance_columns=turf_acceptance_columns())
        assert run.status.value == "failed"
        assert "DataFrame" in run.error_message

    def test_missing_maxdiff_columns_fails(self):
        import packages.survey_analysis.maxdiff_turf  # noqa: F401
        run = create_run("proj-001", RunConfig(analysis_type="maxdiff_turf"), _versions())
        execute_run(run, df=_df(), acceptance_columns=turf_acceptance_columns())
        assert run.status.value == "failed"
        assert "maxdiff_columns" in run.error_message
