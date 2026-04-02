# K-Means Clustering & Segmentation — Agent Instructions

## Purpose

Segment respondents into distinct groups using K-Means clustering, then profile each segment across demographics, attitudes, and behaviors. Always run VarClus first to reduce dimensionality (see `VARCLUS.md`).

---

## Prerequisites

```
pip install pandas numpy scipy scikit-learn openpyxl
```

### Required Inputs

| Input | Source | Description |
|-------|--------|-------------|
| Mapped data file | CSV/Excel | Survey data |
| Clustering variables | Config/mapping | Attitude or motivation battery (preferably VarClus representatives) |
| Profiling variables | Config/mapping | Demographics, behaviors, and attitudes for segment profiling |

---

## When to Use

- You want to discover **natural groupings** in the respondent base
- You have a battery of 10+ attitude/motivation items
- The client needs **segment profiles** for targeting and messaging

### Always VarClus First

Run VarClus (see `VARCLUS.md`) before K-Means to reduce dimensionality. Use cluster representative variables as K-Means inputs rather than raw items. This reduces noise and multicollinearity.

---

## Step-by-Step Workflow

### Step 1: Select k Values to Test

```python
from survey_analysis_toolkit import run_kmeans

kmeans_results = run_kmeans(df, vars_list=clustering_vars, k_values=[3, 4, 5, 6, 7])
```

### Step 2: Evaluate Solutions

Each k value produces:
- **Silhouette score**: Higher = better separation (-1 to 1, target > 0.2)
- **Davies-Bouldin index**: Lower = better (target < 1.5)
- **Cluster sizes**: Check for very small clusters (< 5% of sample)

Choose the k that balances statistical quality with interpretability.

### Step 3: Profile the Selected Solution

```python
from survey_analysis_toolkit import build_cluster_profiles

df['Cluster'] = kmeans_results[5]['labels']  # e.g., k=5
profiles = build_cluster_profiles(
    df, df['Cluster'],
    profile_vars=profile_var_list,
    var_labels=label_dict,
    domains=domain_groupings,
)
```

### Step 4: Write Output

```python
from survey_analysis_toolkit import write_kmeans_excel

write_kmeans_excel(kmeans_results, profiles, var_labels, domains, 'output/kmeans.xlsx')
```

---

## Function Reference

| Function | Parameters | Returns |
|----------|-----------|---------|
| `run_kmeans(df, vars_list, k_values, random_state)` | DataFrame + vars | dict per k: labels, centers, metrics |
| `build_cluster_profiles(df, cluster_labels, profile_vars, var_labels, domains)` | DataFrame + labels | dict of profiles |
| `write_kmeans_excel(results, profiles, var_labels, domains, output_path)` | Results + path | Output path |

---

## Interpretation Guide

- **k selection**: No single "correct" k. Look for the elbow in silhouette scores and ensure each segment is large enough to be actionable (typically > 10% of sample).
- **Segment naming**: Name segments based on their defining attitudes, not demographics. "Culture Seekers" is better than "Young Women."
- **Index scores**: (segment % / total %) x 100. An index of 150 means the segment is 50% more likely than average. Focus on indices > 120 or < 80 for defining characteristics.
