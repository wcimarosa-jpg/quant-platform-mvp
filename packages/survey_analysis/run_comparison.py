"""Run comparison and change diagnostics.

Compares two analysis runs: version/config diffs, metric deltas,
and deterministic causal explanations for significant changes.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .run_orchestrator import AnalysisRun
from .insight_evidence import EvidenceType, InsightBundle, extract_evidence


class ChangeCategory(str, Enum):
    VERSION_CHANGE = "version_change"
    CONFIG_CHANGE = "config_change"
    METRIC_IMPROVEMENT = "metric_improvement"
    METRIC_REGRESSION = "metric_regression"
    METRIC_STABLE = "metric_stable"
    NEW_METRIC = "new_metric"
    REMOVED_METRIC = "removed_metric"


class VersionDiff(BaseModel):
    """Differences in input versions between two runs."""

    field: str
    base_value: Any
    compare_value: Any
    changed: bool


class ConfigDiff(BaseModel):
    """Differences in run configuration."""

    field: str
    base_value: Any
    compare_value: Any
    changed: bool


class MetricDelta(BaseModel):
    """One metric's change between two runs."""

    metric_name: str
    evidence_type: str
    base_value: float | int | str | None
    compare_value: float | int | str | None
    delta: float | None = None
    pct_change: float | None = None
    category: ChangeCategory
    context: dict[str, Any] = Field(default_factory=dict)


class CausalExplanation(BaseModel):
    """Deterministic explanation for a significant metric change."""

    metric_name: str
    explanation: str
    likely_causes: list[str]
    related_version_changes: list[str]
    related_config_changes: list[str]


class RunComparison(BaseModel):
    """Complete comparison between two analysis runs."""

    base_run_id: str
    compare_run_id: str
    analysis_type: str
    version_diffs: list[VersionDiff]
    config_diffs: list[ConfigDiff]
    metric_deltas: list[MetricDelta]
    explanations: list[CausalExplanation]
    summary: str

    def significant_deltas(self, threshold_pct: float = 10.0) -> list[MetricDelta]:
        return [
            d for d in self.metric_deltas
            if d.pct_change is not None and abs(d.pct_change) >= threshold_pct
        ]

    def improvements(self) -> list[MetricDelta]:
        return [d for d in self.metric_deltas if d.category == ChangeCategory.METRIC_IMPROVEMENT]

    def regressions(self) -> list[MetricDelta]:
        return [d for d in self.metric_deltas if d.category == ChangeCategory.METRIC_REGRESSION]


# ---------------------------------------------------------------------------
# Version and config diffing
# ---------------------------------------------------------------------------

def _diff_versions(base: AnalysisRun, compare: AnalysisRun) -> list[VersionDiff]:
    diffs: list[VersionDiff] = []
    for field in ("questionnaire_id", "questionnaire_version", "mapping_id", "mapping_version", "data_file_hash"):
        bv = getattr(base.versions, field)
        cv = getattr(compare.versions, field)
        diffs.append(VersionDiff(field=field, base_value=bv, compare_value=cv, changed=bv != cv))
    return diffs


def _diff_config(base: AnalysisRun, compare: AnalysisRun) -> list[ConfigDiff]:
    diffs: list[ConfigDiff] = []
    diffs.append(ConfigDiff(
        field="analysis_type",
        base_value=base.config.analysis_type,
        compare_value=compare.config.analysis_type,
        changed=base.config.analysis_type != compare.config.analysis_type,
    ))
    for key in sorted(set(list(base.config.parameters.keys()) + list(compare.config.parameters.keys()))):
        bv = base.config.parameters.get(key)
        cv = compare.config.parameters.get(key)
        diffs.append(ConfigDiff(field=f"parameters.{key}", base_value=bv, compare_value=cv, changed=bv != cv))
    return diffs


# ---------------------------------------------------------------------------
# Metric delta computation
# ---------------------------------------------------------------------------

def _compute_deltas(base_bundle: InsightBundle, compare_bundle: InsightBundle) -> list[MetricDelta]:
    deltas: list[MetricDelta] = []

    base_map: dict[str, Any] = {e.metric_name: e for e in base_bundle.evidence}
    compare_map: dict[str, Any] = {e.metric_name: e for e in compare_bundle.evidence}

    all_metrics = set(base_map.keys()) | set(compare_map.keys())

    for metric in sorted(all_metrics):
        base_ev = base_map.get(metric)
        comp_ev = compare_map.get(metric)

        if base_ev and not comp_ev:
            deltas.append(MetricDelta(
                metric_name=metric, evidence_type=base_ev.evidence_type.value,
                base_value=base_ev.value, compare_value=None,
                category=ChangeCategory.REMOVED_METRIC,
                context=base_ev.context,
            ))
            continue

        if comp_ev and not base_ev:
            deltas.append(MetricDelta(
                metric_name=metric, evidence_type=comp_ev.evidence_type.value,
                base_value=None, compare_value=comp_ev.value,
                category=ChangeCategory.NEW_METRIC,
                context=comp_ev.context,
            ))
            continue

        # Both exist
        bv = base_ev.value
        cv = comp_ev.value

        if isinstance(bv, (int, float)) and isinstance(cv, (int, float)):
            delta = round(cv - bv, 4)
            pct = round(delta / abs(bv) * 100, 1) if bv != 0 else None

            # Assumes higher values = improvement (R², correlations, scores).
            # Revisit if error-type metrics (lower=better) are added.
            if abs(delta) < 0.001:
                cat = ChangeCategory.METRIC_STABLE
            elif delta > 0:
                cat = ChangeCategory.METRIC_IMPROVEMENT
            else:
                cat = ChangeCategory.METRIC_REGRESSION

            deltas.append(MetricDelta(
                metric_name=metric, evidence_type=base_ev.evidence_type.value,
                base_value=bv, compare_value=cv, delta=delta, pct_change=pct,
                category=cat, context=comp_ev.context,
            ))
        else:
            cat = ChangeCategory.METRIC_STABLE if bv == cv else ChangeCategory.CONFIG_CHANGE
            deltas.append(MetricDelta(
                metric_name=metric, evidence_type=base_ev.evidence_type.value,
                base_value=bv, compare_value=cv, category=cat,
                context=comp_ev.context,
            ))

    return deltas


# ---------------------------------------------------------------------------
# Causal explanation generator (deterministic)
# ---------------------------------------------------------------------------

def _explain_deltas(
    deltas: list[MetricDelta],
    version_diffs: list[VersionDiff],
    config_diffs: list[ConfigDiff],
) -> list[CausalExplanation]:
    explanations: list[CausalExplanation] = []
    version_changes = [d.field for d in version_diffs if d.changed]
    config_changes = [d.field for d in config_diffs if d.changed]

    significant = [d for d in deltas if d.pct_change is not None and abs(d.pct_change) >= 10.0]

    for delta in significant:
        causes: list[str] = []

        if "data_file_hash" in version_changes:
            causes.append("Data file changed — different respondent sample or cleaning rules.")
        if "mapping_version" in version_changes:
            causes.append("Mapping version changed — variable assignments or scale coding may differ.")
        if "questionnaire_version" in version_changes:
            causes.append("Questionnaire version changed — questions may have been added, removed, or reworded.")
        if config_changes:
            causes.append(f"Config parameters changed: {', '.join(config_changes)}.")
        if not causes:
            causes.append("No version or config changes detected — may reflect natural sample variation.")

        direction = "improved" if delta.category == ChangeCategory.METRIC_IMPROVEMENT else "regressed"
        explanation = (
            f"{delta.metric_name} {direction} by {abs(delta.pct_change or 0):.1f}% "
            f"(from {delta.base_value} to {delta.compare_value})."
        )

        explanations.append(CausalExplanation(
            metric_name=delta.metric_name,
            explanation=explanation,
            likely_causes=causes,
            related_version_changes=version_changes,
            related_config_changes=config_changes,
        ))

    return explanations


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compare_runs(base: AnalysisRun, compare: AnalysisRun) -> RunComparison:
    """Compare two analysis runs end-to-end.

    Both runs must have status=COMPLETED and the same analysis_type.
    """
    if base.status.value != "completed":
        raise ValueError(f"Base run {base.run_id} is not completed (status={base.status.value}).")
    if compare.status.value != "completed":
        raise ValueError(f"Compare run {compare.run_id} is not completed (status={compare.status.value}).")
    if base.config.analysis_type != compare.config.analysis_type:
        raise ValueError(
            f"Cannot compare different analysis types: "
            f"{base.config.analysis_type} vs {compare.config.analysis_type}."
        )

    version_diffs = _diff_versions(base, compare)
    config_diffs = _diff_config(base, compare)

    base_bundle = extract_evidence(base.run_id, base.config.analysis_type, base.result_summary or {})
    compare_bundle = extract_evidence(compare.run_id, compare.config.analysis_type, compare.result_summary or {})

    metric_deltas = _compute_deltas(base_bundle, compare_bundle)
    explanations = _explain_deltas(metric_deltas, version_diffs, config_diffs)

    # Summary
    improvements = [d for d in metric_deltas if d.category == ChangeCategory.METRIC_IMPROVEMENT]
    regressions = [d for d in metric_deltas if d.category == ChangeCategory.METRIC_REGRESSION]
    version_changed = any(d.changed for d in version_diffs)
    summary = (
        f"Comparing {base.run_id} → {compare.run_id}. "
        f"{len(improvements)} improvement(s), {len(regressions)} regression(s). "
        f"{'Input versions changed.' if version_changed else 'Same input versions.'}"
    )

    return RunComparison(
        base_run_id=base.run_id,
        compare_run_id=compare.run_id,
        analysis_type=base.config.analysis_type,
        version_diffs=version_diffs,
        config_diffs=config_diffs,
        metric_deltas=metric_deltas,
        explanations=explanations,
        summary=summary,
    )
