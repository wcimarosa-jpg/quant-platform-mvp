"""Drivers analysis suite: ridge regression, Pearson correlations, weighted-effects.

Identifies which attitudes/perceptions drive behavioral outcomes.
Registered with the run orchestrator as analysis_type="drivers".

Descope (ADR-002): Logistic regression deferred to post-MVP.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from scipy import stats

from .run_orchestrator import AnalysisError, AnalysisRun
from .plugin_contract import register_plugin
from .result_schemas import DriversResultSummary


# ---------------------------------------------------------------------------
# Ridge regression
# ---------------------------------------------------------------------------

def run_ridge(
    df: pd.DataFrame,
    iv_cols: list[str],
    dv_col: str,
    segment_col: str | None = None,
    alpha: float = 0.1,
) -> list[dict[str, Any]]:
    """Run ridge regression for one DV, optionally per segment.

    Returns list of regression result dicts (one per segment + Total).
    """
    results: list[dict[str, Any]] = []
    segments: dict[str, pd.DataFrame] = {"Total": df}

    if segment_col and segment_col in df.columns:
        for val in sorted(df[segment_col].dropna().unique()):
            segments[f"{segment_col}:{val}"] = df[df[segment_col] == val]

    for seg_label, seg_df in segments.items():
        subset = seg_df[iv_cols + [dv_col]].dropna()
        if len(subset) < max(10, len(iv_cols) + 1):
            continue  # skip segments with insufficient data

        X_raw = subset[iv_cols].values
        y = subset[dv_col].values

        # Standardize IVs so coefficients are comparable across scales
        scaler = StandardScaler()
        X = scaler.fit_transform(X_raw)

        model = Ridge(alpha=alpha)
        model.fit(X, y)

        r_squared = float(model.score(X, y))
        n = len(subset)
        p = len(iv_cols)
        # Note: adj_r2 can be negative when model fits poorly — this is statistically valid
        adj_r2 = float(1 - (1 - r_squared) * (n - 1) / (n - p - 1)) if n > p + 1 else None

        coefficients = []
        for i, col in enumerate(iv_cols):
            coef = float(model.coef_[i])
            coefficients.append({
                "variable": col,
                "coefficient": round(coef, 4),
                "std_error": None,
                "p_value": None,
                # Ridge does not produce valid p-values; significant is None.
                # Interpretation should use coefficient magnitude on standardized scale.
                "significant": None,
            })

        results.append({
            "dv_name": dv_col,
            "segment": seg_label,
            "r_squared": round(r_squared, 4),
            "adj_r_squared": round(adj_r2, 4) if adj_r2 is not None else None,
            "n": n,
            "coefficients": coefficients,
        })

    return results


# ---------------------------------------------------------------------------
# Pearson correlations
# ---------------------------------------------------------------------------

def run_pearson(
    df: pd.DataFrame,
    iv_cols: list[str],
    dv_cols: list[str],
) -> list[dict[str, Any]]:
    """Compute Pearson r for each IV×DV pair."""
    results: list[dict[str, Any]] = []
    for iv in iv_cols:
        for dv in dv_cols:
            subset = df[[iv, dv]].dropna()
            if len(subset) < 5:
                continue
            r, p = stats.pearsonr(subset[iv], subset[dv])
            results.append({
                "iv": iv,
                "dv": dv,
                "r": round(float(r), 4),
                "p_value": round(float(p), 6),
                "n": len(subset),
            })
    return results


# ---------------------------------------------------------------------------
# Weighted-effects (multi-DV frequency ranking)
# ---------------------------------------------------------------------------

def run_weighted_effects(
    regressions: list[dict[str, Any]],
    top_n: int = 5,
) -> list[dict[str, Any]]:
    """Count how often each IV appears as a top-N driver across DV×segment combos.

    Args:
        regressions: Output from run_ridge across multiple DVs/segments.
        top_n: How many top drivers to count per regression.
    """
    freq: dict[str, int] = {}
    total_combos = len(regressions)

    for reg in regressions:
        coefs = sorted(reg["coefficients"], key=lambda c: abs(c["coefficient"]), reverse=True)
        for c in coefs[:top_n]:
            freq[c["variable"]] = freq.get(c["variable"], 0) + 1

    results = []
    for var, count in sorted(freq.items(), key=lambda x: x[1], reverse=True):
        results.append({
            "variable": var,
            "top_n_count": count,
            "total_combos": total_combos,
            "frequency_pct": round(count / total_combos * 100, 1) if total_combos > 0 else 0.0,
        })

    return results


# ---------------------------------------------------------------------------
# Registered analysis function
# ---------------------------------------------------------------------------

@register_plugin(
    analysis_type="drivers",
    version="1.0.0",
    description="Ridge regression, Pearson correlations, weighted-effects analysis",
    required_kwargs=["df", "iv_cols", "dv_cols"],
    optional_kwargs=["segment_col", "alpha"],
    result_schema=DriversResultSummary,
    tags=["drivers", "regression", "correlation"],
)
def analysis_drivers(run: AnalysisRun, **kwargs: Any) -> dict[str, Any]:
    """Full drivers suite: ridge + Pearson + weighted-effects.

    Required kwargs:
        df: pd.DataFrame
        iv_cols: list[str]
        dv_cols: list[str]
        segment_col: str | None (optional)
        alpha: float (optional, default 0.1)
    """
    df: pd.DataFrame | None = kwargs.get("df")
    iv_cols: list[str] | None = kwargs.get("iv_cols")
    dv_cols: list[str] | None = kwargs.get("dv_cols")

    if df is None or df.empty:
        raise AnalysisError("DataFrame is required and must not be empty.", "missing_data")
    if not iv_cols:
        raise AnalysisError("iv_cols is required (attitude/motivation battery columns).", "missing_config")
    if not dv_cols:
        raise AnalysisError("dv_cols is required (outcome/DV columns).", "missing_config")

    # Validate columns exist
    missing_iv = [c for c in iv_cols if c not in df.columns]
    if missing_iv:
        raise AnalysisError(f"IV columns not found in data: {missing_iv}", "column_not_found")
    missing_dv = [c for c in dv_cols if c not in df.columns]
    if missing_dv:
        raise AnalysisError(f"DV columns not found in data: {missing_dv}", "column_not_found")

    segment_col = kwargs.get("segment_col")
    alpha = kwargs.get("alpha", 0.1)

    # Ridge across all DVs
    all_regressions: list[dict[str, Any]] = []
    for dv in dv_cols:
        regs = run_ridge(df, iv_cols, dv, segment_col=segment_col, alpha=alpha)
        all_regressions.extend(regs)

    if not all_regressions:
        raise AnalysisError(
            "No regressions produced. Check that data has sufficient non-null rows "
            f"(need at least {len(iv_cols) + 1} per segment).",
            "insufficient_data",
        )

    # Pearson
    pearson = run_pearson(df, iv_cols, dv_cols)

    # Weighted-effects
    weighted = run_weighted_effects(all_regressions, top_n=5)
    top_drivers = [w["variable"] for w in weighted[:10]]

    return {
        "analysis_type": "drivers",
        "regressions": all_regressions,
        "pearson_correlations": pearson,
        "weighted_effects": weighted,
        "top_drivers": top_drivers,
    }
