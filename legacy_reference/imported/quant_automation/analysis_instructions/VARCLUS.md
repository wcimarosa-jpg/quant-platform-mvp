# VarClus Dimension Reduction — Agent Instructions

## Purpose

Reduce a large set of correlated attitude/motivation variables into a smaller set of uncorrelated clusters using VarClus (replication of SAS PROC VARCLUS). This is a prerequisite for K-Means clustering and can also simplify regression models.

---

## Prerequisites

```
pip install pandas numpy scipy scikit-learn openpyxl
```

### Required Inputs

| Input | Source | Description |
|-------|--------|-------------|
| Mapped data file | CSV/Excel | Survey data |
| Variable list | Config/mapping | Battery of items to cluster (e.g., 19 motivation items) |
| Variable labels | Config/mapping | Human-readable labels for each variable |

---

## When to Use

- You have a battery of **10+ correlated items** and need to reduce dimensionality
- As a **prerequisite to K-Means** — use VarClus cluster representatives instead of raw items
- When you need **interpretable groupings** of attitude statements (unlike PCA, VarClus groups are easy to name)

---

## Step-by-Step Workflow

### Step 1: Run VarClus

```python
from survey_analysis_toolkit import run_varclus

varclus_results = run_varclus(
    df,
    vars_list=motivation_vars,
    var_labels=motivation_labels,
    max_eigen=0.5,  # Split threshold — lower = more clusters
)
```

### Step 2: Review Solutions

VarClus produces solutions at each split level. Review:
- **Cluster membership**: Which variables grouped together
- **Eigenvalue of second component**: Below threshold = cluster is stable
- **Representative variable**: The variable most correlated with its cluster's first component

### Step 3: Write Output

```python
from survey_analysis_toolkit import write_varclus_excel

write_varclus_excel(varclus_results, motivation_vars, motivation_labels, len(df), 'output/varclus.xlsx')
```

### Step 4: Use Representatives for Downstream Analysis

Extract cluster representative variables for K-Means or regression:

```python
representatives = [cluster['representative'] for cluster in varclus_results['final_clusters']]
```

---

## Function Reference

| Function | Parameters | Returns |
|----------|-----------|---------|
| `run_varclus(df, vars_list, var_labels, max_eigen)` | DataFrame + vars | dict of solutions at each split level |
| `write_varclus_excel(solutions, var_names, var_labels, n_obs, output_path)` | Results + path | Output path |

---

## Interpretation Guide

- **max_eigen threshold**: 0.5 is a good default. Lower values produce more clusters (finer groupings). Higher values produce fewer clusters (coarser groupings).
- **Naming clusters**: Review the variable labels within each cluster and give it a thematic name (e.g., "Escapism & Relaxation", "Cultural Exploration").
- **1-R² ratio**: Lower = variable fits its cluster well. Variables with high 1-R² may be candidates for their own cluster or removal.
