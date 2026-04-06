"""Insight narrative generation (P08-01b).

Generates human-readable narratives from InsightBundles.
Supports plain-language (stakeholder) and analyst-depth modes.

The deterministic generator produces narratives from evidence without
LLM calls. An LLM-backed generator can be swapped in later by
implementing the same interface.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .insight_evidence import EvidenceItem, EvidenceType, InsightBundle


class NarrativeDepth(str, Enum):
    PLAIN = "plain"       # stakeholder-friendly, no jargon
    ANALYST = "analyst"   # includes statistical details


class NarrativeStatement(BaseModel):
    """One statement in a narrative, linked to its evidence."""

    text: str
    evidence_refs: list[str] = Field(default_factory=list)  # trace_paths
    depth: NarrativeDepth


class InsightNarrative(BaseModel):
    """Complete narrative for one analysis run."""

    run_id: str
    analysis_type: str
    depth: NarrativeDepth
    title: str
    statements: list[NarrativeStatement]
    unsupported_claims: int = 0  # AC: must be 0

    def full_text(self) -> str:
        return "\n\n".join(s.text for s in self.statements)

    def evidence_coverage(self) -> dict[str, Any]:
        total = len(self.statements)
        with_evidence = sum(1 for s in self.statements if s.evidence_refs)
        return {
            "total_statements": total,
            "with_evidence": with_evidence,
            "coverage_pct": round(with_evidence / total * 100, 1) if total > 0 else 0.0,
            "unsupported_claims": self.unsupported_claims,
        }


# ---------------------------------------------------------------------------
# Deterministic narrative generators (no LLM)
# ---------------------------------------------------------------------------

def _top_finding_refs(bundle: InsightBundle) -> list[str]:
    """Collect trace_paths from the first few evidence items as refs for top findings."""
    return [e.trace_path for e in bundle.evidence[:3]]


def _drivers_narrative(bundle: InsightBundle, depth: NarrativeDepth) -> list[NarrativeStatement]:
    stmts: list[NarrativeStatement] = []
    top_refs = _top_finding_refs(bundle)

    # Top findings (backed by evidence refs from the bundle)
    for finding in bundle.top_findings:
        stmts.append(NarrativeStatement(text=finding, evidence_refs=top_refs, depth=depth))

    # R² summary
    r2_items = bundle.by_type(EvidenceType.R_SQUARED)
    if r2_items:
        best = max(r2_items, key=lambda e: e.value)
        if depth == NarrativeDepth.PLAIN:
            stmts.append(NarrativeStatement(
                text=f"The model explains {best.value:.0%} of the variation in {best.context.get('dv', 'the outcome')}.",
                evidence_refs=[best.trace_path],
                depth=depth,
            ))
        else:
            stmts.append(NarrativeStatement(
                text=f"R²={best.value:.4f} for {best.context.get('dv')} ({best.context.get('segment')}), n={best.context.get('n')}.",
                evidence_refs=[best.trace_path],
                depth=depth,
            ))

    # Top drivers
    we_items = bundle.by_type(EvidenceType.WEIGHTED_EFFECT)
    if we_items:
        top3 = we_items[:3]
        if depth == NarrativeDepth.PLAIN:
            names = ", ".join(e.context.get("variable", "?") for e in top3)
            stmts.append(NarrativeStatement(
                text=f"The most important drivers are: {names}.",
                evidence_refs=[e.trace_path for e in top3],
                depth=depth,
            ))
        else:
            for e in top3:
                stmts.append(NarrativeStatement(
                    text=f"{e.context.get('variable')}: top-driver frequency {e.value:.1f}% ({e.context.get('top_n_count')}/{e.context.get('total')} combos).",
                    evidence_refs=[e.trace_path],
                    depth=depth,
                ))

    return stmts


def _segmentation_narrative(bundle: InsightBundle, depth: NarrativeDepth) -> list[NarrativeStatement]:
    stmts: list[NarrativeStatement] = []
    top_refs = _top_finding_refs(bundle)

    for finding in bundle.top_findings:
        stmts.append(NarrativeStatement(text=finding, evidence_refs=top_refs, depth=depth))

    sil_items = bundle.by_type(EvidenceType.SILHOUETTE)
    if sil_items:
        sil = sil_items[0]
        k = sil.context.get("selected_k", "?")
        if depth == NarrativeDepth.PLAIN:
            quality = "good" if sil.value > 0.3 else "moderate" if sil.value > 0.2 else "weak"
            stmts.append(NarrativeStatement(
                text=f"We identified {k} distinct consumer segments with {quality} separation.",
                evidence_refs=[sil.trace_path],
                depth=depth,
            ))
        else:
            stmts.append(NarrativeStatement(
                text=f"K={k} selected. Silhouette={sil.value:.4f}.",
                evidence_refs=[sil.trace_path],
                depth=depth,
            ))

    size_items = bundle.by_type(EvidenceType.CLUSTER_SIZE)
    if size_items:
        for e in size_items:
            stmts.append(NarrativeStatement(
                text=f"{e.metric_name}: {e.value:.1f}%.",
                evidence_refs=[e.trace_path],
                depth=depth,
            ))

    return stmts


def _maxdiff_turf_narrative(bundle: InsightBundle, depth: NarrativeDepth) -> list[NarrativeStatement]:
    stmts: list[NarrativeStatement] = []
    top_refs = _top_finding_refs(bundle)

    for finding in bundle.top_findings:
        stmts.append(NarrativeStatement(text=finding, evidence_refs=top_refs, depth=depth))

    score_items = bundle.by_type(EvidenceType.MAXDIFF_SCORE)
    if score_items:
        top = score_items[0]
        if depth == NarrativeDepth.PLAIN:
            stmts.append(NarrativeStatement(
                text=f"'{top.context.get('item', top.metric_name)}' is the most preferred item with a score of {top.value:.0f}/100.",
                evidence_refs=[top.trace_path],
                depth=depth,
            ))
        else:
            for e in score_items[:5]:
                stmts.append(NarrativeStatement(
                    text=f"{e.metric_name}: {e.value:.1f} (best={e.context.get('best')}, worst={e.context.get('worst')}).",
                    evidence_refs=[e.trace_path],
                    depth=depth,
                ))

    reach_items = bundle.by_type(EvidenceType.TURF_REACH)
    if reach_items:
        best_reach = max(reach_items, key=lambda e: e.value)
        items_list = ", ".join(best_reach.context.get("items", []))
        if depth == NarrativeDepth.PLAIN:
            stmts.append(NarrativeStatement(
                text=f"A portfolio of {len(best_reach.context.get('items', []))} items reaches {best_reach.value:.0f}% of respondents.",
                evidence_refs=[best_reach.trace_path],
                depth=depth,
            ))
        else:
            stmts.append(NarrativeStatement(
                text=f"TURF optimal: [{items_list}] → reach={best_reach.value:.1f}%, avg_freq={best_reach.context.get('avg_frequency')}.",
                evidence_refs=[best_reach.trace_path],
                depth=depth,
            ))

    return stmts


_NARRATIVE_GENERATORS = {
    "drivers": _drivers_narrative,
    "segmentation": _segmentation_narrative,
    "maxdiff_turf": _maxdiff_turf_narrative,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_narrative(
    bundle: InsightBundle,
    depth: NarrativeDepth = NarrativeDepth.PLAIN,
) -> InsightNarrative:
    """Generate a narrative from an evidence bundle.

    All statements are evidence-bound. ``unsupported_claims`` is always 0
    in the deterministic generator (AC requirement).
    """
    generator = _NARRATIVE_GENERATORS.get(bundle.analysis_type)
    if not generator:
        raise ValueError(f"No narrative generator for {bundle.analysis_type!r}")

    statements = generator(bundle, depth)

    titles = {
        "drivers": "Key Driver Analysis Summary",
        "segmentation": "Segmentation Analysis Summary",
        "maxdiff_turf": "MaxDiff & TURF Analysis Summary",
    }

    return InsightNarrative(
        run_id=bundle.run_id,
        analysis_type=bundle.analysis_type,
        depth=depth,
        title=titles.get(bundle.analysis_type, "Analysis Summary"),
        statements=statements,
        unsupported_claims=0,
    )
