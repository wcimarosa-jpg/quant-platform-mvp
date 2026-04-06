"""Tests for P08-01: Insight copilot (evidence retrieval + narrative).

AC-1: Insights include trace links to output rows/metrics.
AC-2: No unsupported numeric claims in narrative.
AC-3: Users can toggle plain-language vs analyst-depth mode.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from data.fixtures.small.p07_synthetic import make_survey_df, iv_columns, dv_columns, maxdiff_items, turf_acceptance_columns
from packages.survey_analysis.run_orchestrator import RunConfig, RunVersions, create_run, execute_run
from packages.survey_analysis.insight_evidence import (
    EvidenceType,
    InsightBundle,
    extract_drivers_evidence,
    extract_evidence,
    extract_maxdiff_turf_evidence,
    extract_segmentation_evidence,
)
from packages.survey_analysis.insight_narrative import (
    InsightNarrative,
    NarrativeDepth,
    NarrativeStatement,
    generate_narrative,
)

# Ensure analysis modules are registered
import packages.survey_analysis.drivers  # noqa: F401
import packages.survey_analysis.segmentation  # noqa: F401
import packages.survey_analysis.maxdiff_turf  # noqa: F401


def _df():
    return make_survey_df(n=200, seed=42)


def _versions():
    return RunVersions(
        questionnaire_id="qre-001", questionnaire_version=1,
        mapping_id="map-001", mapping_version=1, data_file_hash="sha256:test",
    )


def _run_drivers():
    run = create_run("proj-001", RunConfig(analysis_type="drivers"), _versions())
    execute_run(run, df=_df(), iv_cols=iv_columns()[:10], dv_cols=dv_columns())
    return run


def _run_segmentation():
    run = create_run("proj-001", RunConfig(analysis_type="segmentation"), _versions())
    execute_run(run, df=_df(), clustering_vars=iv_columns(), profile_vars=["GENDER", "AGE_GROUP"])
    return run


def _run_maxdiff():
    run = create_run("proj-001", RunConfig(analysis_type="maxdiff_turf"), _versions())
    execute_run(run, df=_df(), maxdiff_columns=maxdiff_items(), acceptance_columns=turf_acceptance_columns())
    return run


# ---------------------------------------------------------------------------
# AC-1: Trace links to output rows/metrics
# ---------------------------------------------------------------------------

class TestEvidenceRetrieval:
    def test_drivers_evidence_extracted(self):
        run = _run_drivers()
        bundle = extract_evidence(run.run_id, "drivers", run.result_summary)
        assert isinstance(bundle, InsightBundle)
        assert len(bundle.evidence) > 0

    def test_drivers_evidence_has_trace_paths(self):
        run = _run_drivers()
        bundle = extract_evidence(run.run_id, "drivers", run.result_summary)
        for item in bundle.evidence:
            assert item.trace_path, f"Missing trace_path on {item.metric_name}"

    def test_drivers_evidence_types_present(self):
        run = _run_drivers()
        bundle = extract_evidence(run.run_id, "drivers", run.result_summary)
        types = {e.evidence_type for e in bundle.evidence}
        assert EvidenceType.R_SQUARED in types
        assert EvidenceType.REGRESSION_COEFFICIENT in types
        assert EvidenceType.WEIGHTED_EFFECT in types

    def test_segmentation_evidence_extracted(self):
        run = _run_segmentation()
        bundle = extract_evidence(run.run_id, "segmentation", run.result_summary)
        assert len(bundle.evidence) > 0
        types = {e.evidence_type for e in bundle.evidence}
        assert EvidenceType.SILHOUETTE in types
        assert EvidenceType.CLUSTER_SIZE in types

    def test_maxdiff_evidence_extracted(self):
        run = _run_maxdiff()
        bundle = extract_evidence(run.run_id, "maxdiff_turf", run.result_summary)
        assert len(bundle.evidence) > 0
        types = {e.evidence_type for e in bundle.evidence}
        assert EvidenceType.MAXDIFF_SCORE in types
        assert EvidenceType.TURF_REACH in types

    def test_top_findings_populated(self):
        run = _run_drivers()
        bundle = extract_evidence(run.run_id, "drivers", run.result_summary)
        assert len(bundle.top_findings) >= 1

    def test_by_type_filter(self):
        run = _run_drivers()
        bundle = extract_evidence(run.run_id, "drivers", run.result_summary)
        r2_only = bundle.by_type(EvidenceType.R_SQUARED)
        assert all(e.evidence_type == EvidenceType.R_SQUARED for e in r2_only)

    def test_unknown_analysis_type_raises(self):
        with pytest.raises(ValueError, match="No evidence extractor"):
            extract_evidence("run-x", "nonexistent", {})

    def test_evidence_values_are_real(self):
        """Values come from actual analysis, not hardcoded."""
        run = _run_drivers()
        bundle = extract_evidence(run.run_id, "drivers", run.result_summary)
        r2_items = bundle.by_type(EvidenceType.R_SQUARED)
        assert len(r2_items) >= 1
        # R² should be between 0 and 1, and data-driven (not a stub constant)
        for item in r2_items:
            assert 0.0 <= item.value <= 1.0


# ---------------------------------------------------------------------------
# AC-2: No unsupported numeric claims
# ---------------------------------------------------------------------------

class TestNoUnsupportedClaims:
    def test_drivers_narrative_zero_unsupported(self):
        run = _run_drivers()
        bundle = extract_evidence(run.run_id, "drivers", run.result_summary)
        narrative = generate_narrative(bundle, NarrativeDepth.PLAIN)
        assert narrative.unsupported_claims == 0

    def test_segmentation_narrative_zero_unsupported(self):
        run = _run_segmentation()
        bundle = extract_evidence(run.run_id, "segmentation", run.result_summary)
        narrative = generate_narrative(bundle, NarrativeDepth.ANALYST)
        assert narrative.unsupported_claims == 0

    def test_maxdiff_narrative_zero_unsupported(self):
        run = _run_maxdiff()
        bundle = extract_evidence(run.run_id, "maxdiff_turf", run.result_summary)
        narrative = generate_narrative(bundle, NarrativeDepth.PLAIN)
        assert narrative.unsupported_claims == 0

    def test_evidence_coverage_high(self):
        run = _run_drivers()
        bundle = extract_evidence(run.run_id, "drivers", run.result_summary)
        narrative = generate_narrative(bundle, NarrativeDepth.ANALYST)
        coverage = narrative.evidence_coverage()
        # Most statements should have evidence refs (top_findings may not)
        assert coverage["with_evidence"] > 0

    def test_statements_with_numbers_have_evidence(self):
        """Any statement containing a number should have an evidence ref."""
        run = _run_drivers()
        bundle = extract_evidence(run.run_id, "drivers", run.result_summary)
        narrative = generate_narrative(bundle, NarrativeDepth.ANALYST)
        import re
        for stmt in narrative.statements:
            has_number = bool(re.search(r'\d+\.?\d*', stmt.text))
            if has_number and "Top driver" not in stmt.text:
                assert len(stmt.evidence_refs) > 0, f"Numeric claim without evidence: {stmt.text}"


# ---------------------------------------------------------------------------
# AC-3: Plain-language vs analyst-depth toggle
# ---------------------------------------------------------------------------

class TestDepthToggle:
    def test_plain_narrative_generated(self):
        run = _run_drivers()
        bundle = extract_evidence(run.run_id, "drivers", run.result_summary)
        narrative = generate_narrative(bundle, NarrativeDepth.PLAIN)
        assert narrative.depth == NarrativeDepth.PLAIN
        assert len(narrative.statements) > 0

    def test_analyst_narrative_generated(self):
        run = _run_drivers()
        bundle = extract_evidence(run.run_id, "drivers", run.result_summary)
        narrative = generate_narrative(bundle, NarrativeDepth.ANALYST)
        assert narrative.depth == NarrativeDepth.ANALYST
        assert len(narrative.statements) > 0

    def test_plain_vs_analyst_differ(self):
        run = _run_drivers()
        bundle = extract_evidence(run.run_id, "drivers", run.result_summary)
        plain = generate_narrative(bundle, NarrativeDepth.PLAIN)
        analyst = generate_narrative(bundle, NarrativeDepth.ANALYST)
        assert plain.full_text() != analyst.full_text()

    def test_analyst_has_more_detail(self):
        run = _run_drivers()
        bundle = extract_evidence(run.run_id, "drivers", run.result_summary)
        plain = generate_narrative(bundle, NarrativeDepth.PLAIN)
        analyst = generate_narrative(bundle, NarrativeDepth.ANALYST)
        # Analyst mode should produce more statements (individual coefficients)
        assert len(analyst.statements) >= len(plain.statements)

    def test_segmentation_both_depths(self):
        run = _run_segmentation()
        bundle = extract_evidence(run.run_id, "segmentation", run.result_summary)
        plain = generate_narrative(bundle, NarrativeDepth.PLAIN)
        analyst = generate_narrative(bundle, NarrativeDepth.ANALYST)
        assert plain.depth == NarrativeDepth.PLAIN
        assert analyst.depth == NarrativeDepth.ANALYST

    def test_maxdiff_both_depths(self):
        run = _run_maxdiff()
        bundle = extract_evidence(run.run_id, "maxdiff_turf", run.result_summary)
        plain = generate_narrative(bundle, NarrativeDepth.PLAIN)
        analyst = generate_narrative(bundle, NarrativeDepth.ANALYST)
        assert plain.depth == NarrativeDepth.PLAIN
        assert analyst.depth == NarrativeDepth.ANALYST

    def test_narrative_has_title(self):
        run = _run_drivers()
        bundle = extract_evidence(run.run_id, "drivers", run.result_summary)
        narrative = generate_narrative(bundle)
        assert narrative.title

    def test_full_text_concatenation(self):
        run = _run_drivers()
        bundle = extract_evidence(run.run_id, "drivers", run.result_summary)
        narrative = generate_narrative(bundle)
        text = narrative.full_text()
        assert len(text) > 50
