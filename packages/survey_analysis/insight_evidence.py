"""Insight evidence retrieval (P08-01a).

Provides structured access to analysis results with trace links
back to specific output rows, metrics, and tables. No LLM calls.
This is the foundation the narrative generator (P08-01b) builds on.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    REGRESSION_COEFFICIENT = "regression_coefficient"
    R_SQUARED = "r_squared"
    PEARSON_CORRELATION = "pearson_correlation"
    WEIGHTED_EFFECT = "weighted_effect"
    CLUSTER_CENTROID = "cluster_centroid"
    CLUSTER_SIZE = "cluster_size"
    SILHOUETTE = "silhouette"
    MAXDIFF_SCORE = "maxdiff_score"
    TURF_REACH = "turf_reach"
    PROFILE_VALUE = "profile_value"


class EvidenceItem(BaseModel):
    """One piece of traceable evidence from an analysis output."""

    evidence_type: EvidenceType
    source_analysis: str          # analysis_type that produced this
    metric_name: str              # human-readable metric label
    value: float | int | str
    context: dict[str, Any] = Field(default_factory=dict)  # segment, DV, variable, etc.
    trace_path: str               # dot-notation path into result_summary


class InsightBundle(BaseModel):
    """A collection of evidence items for one analysis run, ready for narrative."""

    run_id: str
    analysis_type: str
    evidence: list[EvidenceItem]
    top_findings: list[str]       # pre-ranked key finding descriptions (no LLM)

    def by_type(self, etype: EvidenceType) -> list[EvidenceItem]:
        return [e for e in self.evidence if e.evidence_type == etype]

    def by_source(self, analysis_type: str) -> list[EvidenceItem]:
        return [e for e in self.evidence if e.source_analysis == analysis_type]


# ---------------------------------------------------------------------------
# Extractors — pull evidence from typed result summaries
# ---------------------------------------------------------------------------

def extract_drivers_evidence(run_id: str, result: dict[str, Any]) -> InsightBundle:
    """Extract evidence from a drivers result_summary."""
    evidence: list[EvidenceItem] = []
    findings: list[str] = []

    for reg in result.get("regressions", []):
        evidence.append(EvidenceItem(
            evidence_type=EvidenceType.R_SQUARED,
            source_analysis="drivers",
            metric_name=f"R² for {reg['dv_name']} ({reg['segment']})",
            value=reg["r_squared"],
            context={"dv": reg["dv_name"], "segment": reg["segment"], "n": reg["n"]},
            trace_path=f"regressions[dv={reg['dv_name']},seg={reg['segment']}].r_squared",
        ))
        for coef in reg.get("coefficients", [])[:5]:
            evidence.append(EvidenceItem(
                evidence_type=EvidenceType.REGRESSION_COEFFICIENT,
                source_analysis="drivers",
                metric_name=f"{coef['variable']} → {reg['dv_name']}",
                value=coef["coefficient"],
                context={"variable": coef["variable"], "dv": reg["dv_name"], "segment": reg["segment"]},
                trace_path=f"regressions[dv={reg['dv_name']},seg={reg['segment']}].coefficients[{coef['variable']}]",
            ))

    for pc in result.get("pearson_correlations", [])[:10]:
        evidence.append(EvidenceItem(
            evidence_type=EvidenceType.PEARSON_CORRELATION,
            source_analysis="drivers",
            metric_name=f"r({pc['iv']}, {pc['dv']})",
            value=pc["r"],
            context={"iv": pc["iv"], "dv": pc["dv"], "p_value": pc["p_value"], "n": pc["n"]},
            trace_path=f"pearson_correlations[iv={pc['iv']},dv={pc['dv']}].r",
        ))

    for we in result.get("weighted_effects", [])[:5]:
        evidence.append(EvidenceItem(
            evidence_type=EvidenceType.WEIGHTED_EFFECT,
            source_analysis="drivers",
            metric_name=f"{we['variable']} frequency",
            value=we["frequency_pct"],
            context={"variable": we["variable"], "top_n_count": we["top_n_count"], "total": we["total_combos"]},
            trace_path=f"weighted_effects[{we['variable']}].frequency_pct",
        ))

    # Top findings (deterministic, no LLM)
    top_drivers = result.get("top_drivers", [])
    if top_drivers:
        findings.append(f"Top driver: {top_drivers[0]} (appears most frequently across DV×segment combinations).")
    regs = result.get("regressions", [])
    if regs:
        best_r2 = max(regs, key=lambda r: r["r_squared"])
        findings.append(f"Best model fit: R²={best_r2['r_squared']:.3f} for {best_r2['dv_name']} ({best_r2['segment']}).")

    return InsightBundle(run_id=run_id, analysis_type="drivers", evidence=evidence, top_findings=findings)


def extract_segmentation_evidence(run_id: str, result: dict[str, Any]) -> InsightBundle:
    """Extract evidence from a segmentation result_summary."""
    evidence: list[EvidenceItem] = []
    findings: list[str] = []

    evidence.append(EvidenceItem(
        evidence_type=EvidenceType.SILHOUETTE,
        source_analysis="segmentation",
        metric_name="Silhouette score",
        value=result.get("silhouette_score", 0),
        context={"selected_k": result.get("selected_k")},
        trace_path="silhouette_score",
    ))

    for cluster in result.get("kmeans_clusters", []):
        evidence.append(EvidenceItem(
            evidence_type=EvidenceType.CLUSTER_SIZE,
            source_analysis="segmentation",
            metric_name=f"{cluster['label']} size",
            value=cluster["size_pct"],
            context={"cluster_id": cluster["cluster_id"], "size": cluster["size"]},
            trace_path=f"kmeans_clusters[{cluster['cluster_id']}].size_pct",
        ))
        for var, mean_val in list(cluster.get("centroid", {}).items())[:3]:
            evidence.append(EvidenceItem(
                evidence_type=EvidenceType.CLUSTER_CENTROID,
                source_analysis="segmentation",
                metric_name=f"{cluster['label']}: {var}",
                value=mean_val,
                context={"cluster_id": cluster["cluster_id"], "variable": var},
                trace_path=f"kmeans_clusters[{cluster['cluster_id']}].centroid.{var}",
            ))

    for prof in result.get("profile_tables", [])[:5]:
        for seg_label, val in prof.get("values", {}).items():
            evidence.append(EvidenceItem(
                evidence_type=EvidenceType.PROFILE_VALUE,
                source_analysis="segmentation",
                metric_name=f"{prof['variable']} in {seg_label}",
                value=val,
                context={"variable": prof["variable"], "segment": seg_label},
                trace_path=f"profile_tables[{prof['variable']}].values.{seg_label}",
            ))

    k = result.get("selected_k", 0)
    sil = result.get("silhouette_score", 0)
    findings.append(f"Selected {k}-segment solution with silhouette={sil:.3f}.")
    clusters = result.get("kmeans_clusters", [])
    if clusters:
        largest = max(clusters, key=lambda c: c["size"])
        smallest = min(clusters, key=lambda c: c["size"])
        findings.append(f"Largest segment: {largest['label']} ({largest['size_pct']}%). Smallest: {smallest['label']} ({smallest['size_pct']}%).")

    return InsightBundle(run_id=run_id, analysis_type="segmentation", evidence=evidence, top_findings=findings)


def extract_maxdiff_turf_evidence(run_id: str, result: dict[str, Any]) -> InsightBundle:
    """Extract evidence from a maxdiff_turf result_summary."""
    evidence: list[EvidenceItem] = []
    findings: list[str] = []

    for score in result.get("item_scores", [])[:10]:
        evidence.append(EvidenceItem(
            evidence_type=EvidenceType.MAXDIFF_SCORE,
            source_analysis="maxdiff_turf",
            metric_name=f"{score['item']} score",
            value=score["rescaled_score"],
            context={"best": score["best_count"], "worst": score["worst_count"], "diff": score["best_worst_diff"]},
            trace_path=f"item_scores[{score['item']}].rescaled_score",
        ))

    for portfolio in result.get("turf_portfolios", []):
        evidence.append(EvidenceItem(
            evidence_type=EvidenceType.TURF_REACH,
            source_analysis="maxdiff_turf",
            metric_name=f"TURF reach (size={portfolio['portfolio_size']})",
            value=portfolio["reach_pct"],
            context={"items": portfolio["items"], "reach_count": portfolio["reach_count"], "avg_frequency": portfolio["avg_frequency"]},
            trace_path=f"turf_portfolios[size={portfolio['portfolio_size']}].reach_pct",
        ))

    ranking = result.get("item_ranking", [])
    if ranking:
        findings.append(f"Top-ranked item: {ranking[0]}. Bottom-ranked: {ranking[-1]}.")
    optimal = result.get("optimal_portfolio")
    if optimal:
        findings.append(f"Optimal portfolio ({optimal['portfolio_size']} items) reaches {optimal['reach_pct']}% of respondents.")

    return InsightBundle(run_id=run_id, analysis_type="maxdiff_turf", evidence=evidence, top_findings=findings)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_EXTRACTORS = {
    "drivers": extract_drivers_evidence,
    "segmentation": extract_segmentation_evidence,
    "maxdiff_turf": extract_maxdiff_turf_evidence,
}


def extract_evidence(run_id: str, analysis_type: str, result_summary: dict[str, Any]) -> InsightBundle:
    """Extract an InsightBundle from any supported analysis result."""
    extractor = _EXTRACTORS.get(analysis_type)
    if not extractor:
        raise ValueError(f"No evidence extractor for analysis_type={analysis_type!r}. Registered: {list(_EXTRACTORS.keys())}")
    return extractor(run_id, result_summary)
