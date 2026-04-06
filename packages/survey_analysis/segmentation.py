"""Segmentation suite: VarClus + KMeans + profile tables.

VarClus reduces a correlated attitude battery into interpretable clusters,
selects representative variables, then KMeans clusters respondents.
Profile tables summarize each segment across demographics and behaviors.

Registered as a composite analysis: VarClus step → KMeans step.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.linalg import eigh
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from .run_orchestrator import AnalysisError, AnalysisRun
from .plugin_contract import register_composite_plugin
from .result_schemas import SegmentationResultSummary


# ---------------------------------------------------------------------------
# VarClus — hierarchical variable clustering
# ---------------------------------------------------------------------------

def _pca_split(df_subset: pd.DataFrame) -> tuple[float, np.ndarray, np.ndarray]:
    """Compute eigenvalues (descending) and first component loadings.

    Returns (second_eigenvalue, first_component_loadings, all_eigenvalues).
    """
    X = df_subset.values
    X = X - X.mean(axis=0)
    cov = np.cov(X, rowvar=False)
    eigenvalues, eigenvectors = eigh(cov)
    # eigh returns ascending order; we want descending
    idx = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]
    second_eigen = float(eigenvalues[1]) if len(eigenvalues) > 1 else 0.0
    loadings = eigenvectors[:, 0]
    return second_eigen, loadings, eigenvalues


def run_varclus(
    df: pd.DataFrame,
    vars_list: list[str],
    max_eigen: float = 0.5,
) -> list[dict[str, Any]]:
    """Run VarClus variable clustering.

    Iteratively splits variable clusters until no cluster's second
    eigenvalue exceeds max_eigen.

    Returns list of cluster dicts with variables, representative, eigenvalue.
    """
    if not vars_list:
        raise AnalysisError("vars_list is required (attitude battery columns).", "missing_config")
    missing = [v for v in vars_list if v not in df.columns]
    if missing:
        raise AnalysisError(f"Variables not found in data: {missing}", "column_not_found")

    subset = df[vars_list].dropna()
    if len(subset) < 10:
        raise AnalysisError("Fewer than 10 complete rows for VarClus.", "insufficient_data")

    # Start with all variables in one cluster
    clusters: list[list[str]] = [list(vars_list)]

    changed = True
    while changed:
        changed = False
        new_clusters: list[list[str]] = []
        for cluster_vars in clusters:
            if len(cluster_vars) < 2:
                new_clusters.append(cluster_vars)
                continue

            second_eigen, loadings, _ = _pca_split(subset[cluster_vars])
            if second_eigen > max_eigen:
                # Simplified VarClus: split by sign of PC1 loadings (canonical SAS uses PC2).
                pos = [v for v, l in zip(cluster_vars, loadings) if l >= 0]
                neg = [v for v, l in zip(cluster_vars, loadings) if l < 0]
                if pos and neg:
                    new_clusters.append(pos)
                    new_clusters.append(neg)
                    changed = True
                else:
                    new_clusters.append(cluster_vars)
            else:
                new_clusters.append(cluster_vars)
        clusters = new_clusters

    # Build output with representatives
    results: list[dict[str, Any]] = []
    for i, cluster_vars in enumerate(clusters):
        if len(cluster_vars) == 1:
            rep = cluster_vars[0]
            eigen = 0.0
            var_exp = 1.0
        else:
            # Representative = variable with highest correlation to cluster mean
            cluster_data = subset[cluster_vars]
            cluster_mean = cluster_data.mean(axis=1)
            correlations = {v: float(cluster_data[v].corr(cluster_mean)) for v in cluster_vars}
            rep = max(correlations, key=lambda v: correlations[v])

            # Reuse _pca_split to get eigenvalues (avoids redundant computation)
            second_eigen, _, all_eigenvalues = _pca_split(cluster_data)
            eigen = second_eigen
            total_var = float(all_eigenvalues.sum())
            var_exp = float(all_eigenvalues[0] / total_var) if total_var > 0 else 0.0

        results.append({
            "cluster_id": i + 1,
            "variables": cluster_vars,
            "representative": rep,
            "eigenvalue": round(eigen, 4),
            "variance_explained": round(var_exp, 4),
        })

    return results


# ---------------------------------------------------------------------------
# KMeans clustering
# ---------------------------------------------------------------------------

def run_kmeans(
    df: pd.DataFrame,
    clustering_vars: list[str],
    k_values: list[int] | None = None,
    random_state: int = 42,
) -> dict[str, Any]:
    """Run KMeans sweep across k values, select best by silhouette.

    Returns dict with selected_k, silhouette_score, cluster assignments, centroids.
    """
    if not clustering_vars:
        raise AnalysisError("clustering_vars is required.", "missing_config")
    missing = [v for v in clustering_vars if v not in df.columns]
    if missing:
        raise AnalysisError(f"Clustering variables not found: {missing}", "column_not_found")

    subset = df[clustering_vars].dropna()
    if len(subset) < 20:
        raise AnalysisError("Fewer than 20 complete rows for KMeans.", "insufficient_data")

    if k_values is None:
        k_values = [3, 4, 5, 6]

    scaler = StandardScaler()
    X = scaler.fit_transform(subset.values)

    best_k = k_values[0]
    best_sil = -1.0
    best_labels = None
    best_model = None
    sil_scores: dict[int, float] = {}

    for k in k_values:
        if k < 2 or k >= len(X):
            continue
        model = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        labels = model.fit_predict(X)
        sil = float(silhouette_score(X, labels))
        sil_scores[k] = round(sil, 4)
        if sil > best_sil:
            best_sil = sil
            best_k = k
            best_labels = labels
            best_model = model

    if best_labels is None:
        raise AnalysisError("KMeans produced no valid solution.", "computation_error")

    # Build cluster info
    clusters: list[dict[str, Any]] = []
    for c_id in range(best_k):
        mask = best_labels == c_id
        size = int(mask.sum())
        centroid = {
            var: round(float(subset.loc[subset.index[mask], var].mean()), 3)
            for var in clustering_vars
        }
        clusters.append({
            "cluster_id": c_id + 1,
            "label": f"Segment {c_id + 1}",
            "size": size,
            "size_pct": round(size / len(subset) * 100, 1),
            "centroid": centroid,
        })

    return {
        "selected_k": best_k,
        "silhouette_score": round(best_sil, 4),
        "k_candidates": k_values,
        "silhouette_scores": sil_scores,
        "kmeans_clusters": clusters,
        "cluster_assignments": best_labels.tolist(),
        "row_index": subset.index.tolist(),
    }


# ---------------------------------------------------------------------------
# Profile tables
# ---------------------------------------------------------------------------

def build_profiles(
    df: pd.DataFrame,
    cluster_assignments: list[int],
    row_index: list[int],
    profile_vars: list[str],
    cluster_labels: dict[int, str] | None = None,
) -> list[dict[str, Any]]:
    """Build segment profile tables: mean/% of each profile variable per segment."""
    if not profile_vars:
        return []

    profile_df = df.loc[row_index].copy()
    profile_df["_segment"] = cluster_assignments

    segments = sorted(profile_df["_segment"].unique())
    if cluster_labels is None:
        cluster_labels = {s: f"Segment {s + 1}" for s in segments}

    profiles: list[dict[str, Any]] = []
    for var in profile_vars:
        if var not in profile_df.columns:
            continue
        values: dict[str, float] = {}
        for seg in segments:
            seg_data = profile_df[profile_df["_segment"] == seg][var].dropna()
            if len(seg_data) > 0:
                values[cluster_labels.get(seg, f"Seg {seg + 1}")] = round(float(seg_data.mean()), 3)
        profiles.append({
            "variable": var,
            "variable_label": None,
            "values": values,
        })

    return profiles


# ---------------------------------------------------------------------------
# Composite registration: VarClus step → KMeans step
# ---------------------------------------------------------------------------

def _step_varclus(run: AnalysisRun, previous_results: dict | None = None, **kwargs: Any) -> dict[str, Any]:
    """VarClus step — returns varclus_clusters and varclus_representatives."""
    df: pd.DataFrame | None = kwargs.get("df")
    vars_list: list[str] | None = kwargs.get("clustering_vars") or kwargs.get("vars_list")
    max_eigen: float = kwargs.get("max_eigen", 0.5)

    if df is None or df.empty:
        raise AnalysisError("DataFrame is required.", "missing_data")
    if not vars_list:
        raise AnalysisError("clustering_vars is required.", "missing_config")

    clusters = run_varclus(df, vars_list, max_eigen=max_eigen)
    representatives = [c["representative"] for c in clusters]

    return {
        "analysis_type": "segmentation",
        "varclus_clusters": clusters,
        "varclus_representatives": representatives,
    }


def _step_kmeans(run: AnalysisRun, previous_results: dict | None = None, **kwargs: Any) -> dict[str, Any]:
    """KMeans step — reads representatives from VarClus, clusters respondents, builds profiles."""
    df: pd.DataFrame | None = kwargs.get("df")
    if df is None:
        raise AnalysisError("DataFrame is required.", "missing_data")

    prev = previous_results or {}
    clustering_vars = prev.get("varclus_representatives") or kwargs.get("clustering_vars", [])
    k_values = kwargs.get("k_values")
    profile_vars = kwargs.get("profile_vars", [])

    kmeans_result = run_kmeans(df, clustering_vars, k_values=k_values)

    profiles = build_profiles(
        df,
        kmeans_result["cluster_assignments"],
        kmeans_result["row_index"],
        profile_vars,
    )

    return {
        "selected_k": kmeans_result["selected_k"],
        "silhouette_score": kmeans_result["silhouette_score"],
        "kmeans_clusters": kmeans_result["kmeans_clusters"],
        "profile_tables": profiles,
    }


# Register composite: VarClus → KMeans
register_composite_plugin(
    analysis_type="segmentation",
    steps=[_step_varclus, _step_kmeans],
    version="1.0.0",
    description="VarClus variable clustering + KMeans respondent segmentation + profile tables",
    required_kwargs=["df", "attitude_cols"],
    optional_kwargs=["segment_col", "max_k", "min_k"],
    result_schema=SegmentationResultSummary,
    tags=["segmentation", "clustering", "composite"],
)
