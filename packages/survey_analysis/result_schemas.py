"""Shared analysis result schemas.

Typed result models for each analysis type. These schemas define the
contract between P07 analysis modules and P08 consumers (insight copilot,
run comparison). Every analysis function registered via @register_analysis
must return a dict that validates against the corresponding schema.

Descope decisions (MVP):
- MaxDiff uses count-based scoring, not HB MCMC estimation.
- Logistic regression deferred; drivers suite covers ridge + Pearson + weighted-effects.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Drivers (P07-02): ridge, Pearson, weighted-effects
# ---------------------------------------------------------------------------

class CoefficientRow(BaseModel):
    """One IV coefficient from a regression model."""

    variable: str
    coefficient: float
    std_error: float | None = None
    p_value: float | None = None
    significant: bool = False


class RegressionResult(BaseModel):
    """Output of one ridge regression (single DV, single segment)."""

    dv_name: str
    segment: str  # "Total" or segment label
    r_squared: float
    adj_r_squared: float | None = None
    n: int
    coefficients: list[CoefficientRow]


class PearsonRow(BaseModel):
    """One Pearson correlation pair."""

    iv: str
    dv: str
    r: float
    p_value: float
    n: int


class WeightedEffectsRow(BaseModel):
    """One IV's weighted-effects score across multiple DVs."""

    variable: str
    top_n_count: int       # how many DV×segment combos this IV was a top driver
    total_combos: int      # total DV×segment combos tested
    frequency_pct: float   # top_n_count / total_combos * 100


class DriversResultSummary(BaseModel):
    """Complete drivers suite output (P07-02)."""

    analysis_type: str = "drivers"
    regressions: list[RegressionResult]
    pearson_correlations: list[PearsonRow]
    weighted_effects: list[WeightedEffectsRow]
    top_drivers: list[str]  # ordered by weighted-effects frequency


# ---------------------------------------------------------------------------
# Segmentation (P07-03): VarClus + KMeans + profiles
# ---------------------------------------------------------------------------

class VarClusCluster(BaseModel):
    """One variable cluster from VarClus."""

    cluster_id: int
    variables: list[str]
    representative: str      # variable with highest R² to cluster
    eigenvalue: float
    variance_explained: float


class KMeansCluster(BaseModel):
    """One K-Means segment."""

    cluster_id: int
    label: str               # auto or user-assigned name
    size: int
    size_pct: float
    centroid: dict[str, float]  # variable → mean


class ProfileRow(BaseModel):
    """One row in a segment profile table."""

    variable: str
    variable_label: str | None = None
    values: dict[str, float]  # segment_label → value (mean, %, etc.)


class SegmentationResultSummary(BaseModel):
    """Complete segmentation suite output (P07-03)."""

    analysis_type: str = "segmentation"
    varclus_clusters: list[VarClusCluster]
    selected_k: int
    silhouette_score: float
    kmeans_clusters: list[KMeansCluster]
    profile_tables: list[ProfileRow]


# ---------------------------------------------------------------------------
# MaxDiff + TURF (P07-04): count-based scoring + reach optimization
# ---------------------------------------------------------------------------

class MaxDiffItemScore(BaseModel):
    """One item's MaxDiff utility score (count-based)."""

    item: str
    best_count: int
    worst_count: int
    best_worst_diff: int
    rescaled_score: float    # 0-100 scale


class TURFPortfolio(BaseModel):
    """One TURF portfolio solution."""

    portfolio_size: int
    items: list[str]
    reach_count: int
    reach_pct: float
    avg_frequency: float


class MaxDiffTURFResultSummary(BaseModel):
    """Complete MaxDiff + TURF output (P07-04)."""

    analysis_type: str = "maxdiff_turf"
    item_scores: list[MaxDiffItemScore]     # sorted by rescaled_score desc
    item_ranking: list[str]                  # item names in rank order
    turf_portfolios: list[TURFPortfolio]     # one per portfolio size tested
    optimal_portfolio: TURFPortfolio | None = None


# ---------------------------------------------------------------------------
# Registry: analysis_type → schema class
# ---------------------------------------------------------------------------

RESULT_SCHEMAS: dict[str, type[BaseModel]] = {
    "drivers": DriversResultSummary,
    "segmentation": SegmentationResultSummary,
    "maxdiff_turf": MaxDiffTURFResultSummary,
}


def validate_result(analysis_type: str, result_dict: dict[str, Any]) -> BaseModel:
    """Validate a result_summary dict against the expected schema.

    Raises ValidationError if the dict does not conform.
    """
    schema_cls = RESULT_SCHEMAS.get(analysis_type)
    if not schema_cls:
        raise ValueError(f"No result schema registered for analysis_type: {analysis_type!r}")
    return schema_cls.model_validate(result_dict)
