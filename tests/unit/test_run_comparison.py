"""Tests for P08-02: Run comparison and change diagnostics.

AC-1: Run diff view shows input/config/version changes.
AC-2: Key metric deltas are computed and displayed.
AC-3: Assistant can explain likely causes of major deltas.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from data.fixtures.small.p07_synthetic import make_survey_df, iv_columns, dv_columns
from packages.survey_analysis.run_comparison import (
    ChangeCategory,
    RunComparison,
    compare_runs,
)
from packages.survey_analysis.run_orchestrator import (
    RunConfig,
    RunVersions,
    create_run,
    execute_run,
)

import packages.survey_analysis.drivers  # noqa: F401


def _versions(**overrides) -> RunVersions:
    defaults = dict(
        questionnaire_id="qre-001", questionnaire_version=1,
        mapping_id="map-001", mapping_version=1, data_file_hash="sha256:abc",
    )
    defaults.update(overrides)
    return RunVersions(**defaults)


def _run_drivers(seed: int = 42, **version_overrides):
    df = make_survey_df(n=200, seed=seed)
    run = create_run("proj-001", RunConfig(analysis_type="drivers"), _versions(**version_overrides))
    execute_run(run, df=df, iv_cols=iv_columns()[:10], dv_cols=dv_columns())
    assert run.status.value == "completed"
    return run


# ---------------------------------------------------------------------------
# AC-1: Version/config diff
# ---------------------------------------------------------------------------

class TestVersionDiff:
    def test_identical_runs_no_version_changes(self):
        r1 = _run_drivers(seed=42)
        r2 = _run_drivers(seed=42)
        comp = compare_runs(r1, r2)
        changed = [d for d in comp.version_diffs if d.changed]
        assert len(changed) == 0

    def test_mapping_version_change_detected(self):
        r1 = _run_drivers(seed=42, mapping_version=1)
        r2 = _run_drivers(seed=42, mapping_version=2)
        comp = compare_runs(r1, r2)
        mv_diff = next(d for d in comp.version_diffs if d.field == "mapping_version")
        assert mv_diff.changed is True
        assert mv_diff.base_value == 1
        assert mv_diff.compare_value == 2

    def test_data_file_change_detected(self):
        r1 = _run_drivers(seed=42, data_file_hash="sha256:aaa")
        r2 = _run_drivers(seed=42, data_file_hash="sha256:bbb")
        comp = compare_runs(r1, r2)
        hash_diff = next(d for d in comp.version_diffs if d.field == "data_file_hash")
        assert hash_diff.changed is True

    def test_config_diff_same_type(self):
        r1 = _run_drivers(seed=42)
        r2 = _run_drivers(seed=42)
        comp = compare_runs(r1, r2)
        type_diff = next(d for d in comp.config_diffs if d.field == "analysis_type")
        assert type_diff.changed is False

    def test_cannot_compare_different_types(self):
        import packages.survey_analysis.maxdiff_turf  # noqa: F401
        from data.fixtures.small.p07_synthetic import maxdiff_items, turf_acceptance_columns
        r1 = _run_drivers(seed=42)
        r2 = create_run("proj-001", RunConfig(analysis_type="maxdiff_turf"), _versions())
        execute_run(r2, df=make_survey_df(), maxdiff_columns=maxdiff_items(), acceptance_columns=turf_acceptance_columns())
        with pytest.raises(ValueError, match="different analysis types"):
            compare_runs(r1, r2)

    def test_cannot_compare_non_completed(self):
        r1 = _run_drivers(seed=42)
        r2 = create_run("proj-001", RunConfig(analysis_type="drivers"), _versions())
        # r2 is QUEUED, not completed
        with pytest.raises(ValueError, match="not completed"):
            compare_runs(r1, r2)


# ---------------------------------------------------------------------------
# AC-2: Metric deltas
# ---------------------------------------------------------------------------

class TestMetricDeltas:
    def test_identical_data_stable_metrics(self):
        r1 = _run_drivers(seed=42)
        r2 = _run_drivers(seed=42)
        comp = compare_runs(r1, r2)
        stable = [d for d in comp.metric_deltas if d.category == ChangeCategory.METRIC_STABLE]
        assert len(stable) > 0

    def test_different_data_produces_deltas(self):
        r1 = _run_drivers(seed=42)
        r2 = _run_drivers(seed=99)  # different seed = different data
        comp = compare_runs(r1, r2)
        non_stable = [d for d in comp.metric_deltas if d.category != ChangeCategory.METRIC_STABLE]
        assert len(non_stable) > 0

    def test_deltas_have_values(self):
        r1 = _run_drivers(seed=42)
        r2 = _run_drivers(seed=99)
        comp = compare_runs(r1, r2)
        for d in comp.metric_deltas:
            assert d.metric_name
            assert d.evidence_type

    def test_improvements_and_regressions(self):
        r1 = _run_drivers(seed=42)
        r2 = _run_drivers(seed=99)
        comp = compare_runs(r1, r2)
        assert len(comp.metric_deltas) > 0
        # Verify improvements/regressions return correct categories
        for d in comp.improvements():
            assert d.category == ChangeCategory.METRIC_IMPROVEMENT
        for d in comp.regressions():
            assert d.category == ChangeCategory.METRIC_REGRESSION

    def test_significant_deltas_filter(self):
        r1 = _run_drivers(seed=42)
        r2 = _run_drivers(seed=99)
        comp = compare_runs(r1, r2)
        sig = comp.significant_deltas(threshold_pct=5.0)
        for d in sig:
            assert abs(d.pct_change) >= 5.0

    def test_delta_has_pct_change(self):
        r1 = _run_drivers(seed=42)
        r2 = _run_drivers(seed=99)
        comp = compare_runs(r1, r2)
        numeric_deltas = [d for d in comp.metric_deltas if d.delta is not None]
        assert len(numeric_deltas) > 0
        for d in numeric_deltas:
            assert isinstance(d.delta, float)


# ---------------------------------------------------------------------------
# AC-3: Causal explanations
# ---------------------------------------------------------------------------

class TestCausalExplanations:
    def test_explanations_for_version_change(self):
        r1 = _run_drivers(seed=42, data_file_hash="sha256:old")
        r2 = _run_drivers(seed=99, data_file_hash="sha256:new")
        comp = compare_runs(r1, r2)
        # Different data + hash should produce significant deltas with explanations
        assert len(comp.explanations) > 0, "Expected explanations for different data + hash"
        for exp in comp.explanations:
            assert exp.explanation
            assert len(exp.likely_causes) >= 1
            assert "data_file_hash" in exp.related_version_changes

    def test_explanations_reference_metric(self):
        r1 = _run_drivers(seed=42, mapping_version=1)
        r2 = _run_drivers(seed=99, mapping_version=2)
        comp = compare_runs(r1, r2)
        for exp in comp.explanations:
            assert exp.metric_name
            assert "mapping" in " ".join(exp.likely_causes).lower() or "Mapping" in " ".join(exp.likely_causes)

    def test_no_explanations_for_identical_runs(self):
        r1 = _run_drivers(seed=42)
        r2 = _run_drivers(seed=42)
        comp = compare_runs(r1, r2)
        assert len(comp.explanations) == 0

    def test_explanation_includes_direction(self):
        r1 = _run_drivers(seed=42, data_file_hash="sha256:v1")
        r2 = _run_drivers(seed=99, data_file_hash="sha256:v2")
        comp = compare_runs(r1, r2)
        for exp in comp.explanations:
            assert "improved" in exp.explanation or "regressed" in exp.explanation


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class TestSummary:
    def test_summary_has_run_ids(self):
        r1 = _run_drivers(seed=42)
        r2 = _run_drivers(seed=42)
        comp = compare_runs(r1, r2)
        assert r1.run_id in comp.summary
        assert r2.run_id in comp.summary

    def test_summary_mentions_improvements_regressions(self):
        r1 = _run_drivers(seed=42)
        r2 = _run_drivers(seed=99)
        comp = compare_runs(r1, r2)
        assert "improvement" in comp.summary or "regression" in comp.summary

    def test_summary_notes_version_change(self):
        r1 = _run_drivers(seed=42, data_file_hash="sha256:a")
        r2 = _run_drivers(seed=42, data_file_hash="sha256:b")
        comp = compare_runs(r1, r2)
        assert "versions changed" in comp.summary

    def test_summary_notes_same_versions(self):
        r1 = _run_drivers(seed=42)
        r2 = _run_drivers(seed=42)
        comp = compare_runs(r1, r2)
        assert "Same input versions" in comp.summary
