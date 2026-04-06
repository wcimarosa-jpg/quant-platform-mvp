"""MaxDiff count-based scoring + TURF greedy reach optimization.

MaxDiff: Computes best/worst counts and rescaled 0-100 scores from
best-worst task data (coded as best=1, worst=-1, not_shown=0).

TURF: Greedy incremental reach algorithm on a binary acceptance matrix.
Tie-breaking: individual reach descending, then alphabetical.

Descope (ADR-002): HB MCMC estimation deferred. Count-based only.
Frequency optimization metric deferred. Reach only.

Registered with run orchestrator as analysis_type="maxdiff_turf".
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .run_orchestrator import AnalysisError, AnalysisRun, register_analysis


# ---------------------------------------------------------------------------
# MaxDiff count-based scoring
# ---------------------------------------------------------------------------

def score_maxdiff(
    df: pd.DataFrame,
    item_columns: list[str],
    item_labels: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Compute count-based MaxDiff scores.

    Each column should be coded: 1=best, -1=worst, 0=not shown/not selected.

    Returns list of item score dicts sorted by rescaled_score descending.
    """
    if not item_columns:
        raise AnalysisError("item_columns is required for MaxDiff scoring.", "missing_config")
    missing = [c for c in item_columns if c not in df.columns]
    if missing:
        raise AnalysisError(f"MaxDiff item columns not found: {missing}", "column_not_found")

    labels = item_labels or {}
    scores: list[dict[str, Any]] = []

    for col in item_columns:
        series = df[col].dropna()
        best_count = int((series == 1).sum())
        worst_count = int((series == -1).sum())
        diff = best_count - worst_count
        scores.append({
            "item": labels.get(col, col),
            "best_count": best_count,
            "worst_count": worst_count,
            "best_worst_diff": diff,
            "rescaled_score": 0.0,  # placeholder, rescaled below
        })

    # Rescale to 0-100
    if scores:
        diffs = [s["best_worst_diff"] for s in scores]
        min_diff = min(diffs)
        max_diff = max(diffs)
        rng = max_diff - min_diff
        for s in scores:
            s["rescaled_score"] = round(
                (s["best_worst_diff"] - min_diff) / rng * 100 if rng > 0 else 50.0, 1
            )

    scores.sort(key=lambda s: s["rescaled_score"], reverse=True)
    return scores


# ---------------------------------------------------------------------------
# TURF greedy incremental reach
# ---------------------------------------------------------------------------

def run_turf(
    df: pd.DataFrame,
    acceptance_columns: list[str],
    item_labels: dict[str, str] | None = None,
    portfolio_sizes: list[int] | None = None,
) -> list[dict[str, Any]]:
    """Greedy TURF: find optimal portfolios maximizing unduplicated reach.

    ``acceptance_columns``: binary (0/1) columns, one per item.
    Tie-breaking: individual reach descending, then alphabetical item name.

    Returns list of TURFPortfolio dicts, one per portfolio size.
    """
    if not acceptance_columns:
        raise AnalysisError("acceptance_columns is required for TURF.", "missing_config")
    missing = [c for c in acceptance_columns if c not in df.columns]
    if missing:
        raise AnalysisError(f"TURF acceptance columns not found: {missing}", "column_not_found")

    labels = item_labels or {}
    if portfolio_sizes is None:
        portfolio_sizes = list(range(1, min(len(acceptance_columns) + 1, 8)))

    n = len(df)
    if n == 0:
        raise AnalysisError("DataFrame is empty for TURF.", "insufficient_data")

    # Precompute binary acceptance matrix as numpy
    accept_matrix = df[acceptance_columns].fillna(0).values.astype(bool)  # n × m
    item_names = [labels.get(c, c) for c in acceptance_columns]

    # Individual reach for tie-breaking
    individual_reach = {
        item_names[i]: int(accept_matrix[:, i].sum())
        for i in range(len(acceptance_columns))
    }

    portfolios: list[dict[str, Any]] = []

    for target_size in portfolio_sizes:
        if target_size < 1 or target_size > len(acceptance_columns):
            continue

        selected_indices: list[int] = []
        reached = np.zeros(n, dtype=bool)

        for _ in range(target_size):
            best_idx = -1
            best_incremental = -1
            best_name = ""

            for i in range(len(acceptance_columns)):
                if i in selected_indices:
                    continue
                incremental = int((accept_matrix[:, i] & ~reached).sum())
                name = item_names[i]

                # Tie-breaking: incremental reach, then individual reach, then alphabetical
                if (incremental > best_incremental or
                    (incremental == best_incremental and
                     individual_reach[name] > individual_reach.get(best_name, -1)) or
                    (incremental == best_incremental and
                     individual_reach[name] == individual_reach.get(best_name, -1) and
                     name < best_name)):
                    best_idx = i
                    best_incremental = incremental
                    best_name = name

            if best_idx < 0:
                break

            selected_indices.append(best_idx)
            reached |= accept_matrix[:, best_idx]

        selected_names = [item_names[i] for i in selected_indices]
        reach_count = int(reached.sum())
        reach_pct = round(reach_count / n * 100, 1)

        # Average frequency among reached respondents
        if reach_count > 0:
            freq_matrix = accept_matrix[reached][:, selected_indices]
            avg_freq = round(float(freq_matrix.sum()) / reach_count, 2)
        else:
            avg_freq = 0.0

        portfolios.append({
            "portfolio_size": len(selected_indices),
            "items": selected_names,
            "reach_count": reach_count,
            "reach_pct": reach_pct,
            "avg_frequency": avg_freq,
        })

    return portfolios


# ---------------------------------------------------------------------------
# Registered analysis function
# ---------------------------------------------------------------------------

@register_analysis("maxdiff_turf")
def analysis_maxdiff_turf(run: AnalysisRun, **kwargs: Any) -> dict[str, Any]:
    """Full MaxDiff + TURF suite.

    Required kwargs:
        df: pd.DataFrame
        maxdiff_columns: list[str] — coded 1/0/-1
        acceptance_columns: list[str] — binary 0/1
    Optional:
        item_labels: dict[str, str]
        portfolio_sizes: list[int]
    """
    df: pd.DataFrame | None = kwargs.get("df")
    maxdiff_columns: list[str] | None = kwargs.get("maxdiff_columns")
    acceptance_columns: list[str] | None = kwargs.get("acceptance_columns")

    if df is None or df.empty:
        raise AnalysisError("DataFrame is required and must not be empty.", "missing_data")
    if not maxdiff_columns:
        raise AnalysisError("maxdiff_columns is required.", "missing_config")
    if not acceptance_columns:
        raise AnalysisError("acceptance_columns is required.", "missing_config")

    item_labels = kwargs.get("item_labels", {})
    portfolio_sizes = kwargs.get("portfolio_sizes")

    # MaxDiff scoring
    item_scores = score_maxdiff(df, maxdiff_columns, item_labels)
    item_ranking = [s["item"] for s in item_scores]

    # TURF
    turf_portfolios = run_turf(df, acceptance_columns, item_labels, portfolio_sizes)

    # Best portfolio = largest reach_pct
    optimal = max(turf_portfolios, key=lambda p: p["reach_pct"]) if turf_portfolios else None

    return {
        "analysis_type": "maxdiff_turf",
        "total_respondents": len(df),
        "item_scores": item_scores,
        "item_ranking": item_ranking,
        "turf_portfolios": turf_portfolios,
        "optimal_portfolio": optimal,
    }
