# Ridge Regression & Multi-DV Key Driver Analysis — Agent Instructions

## Purpose

Identify which attitudes, motivations, or perceptions drive behavioral outcomes using Ridge regression. The multi-DV approach runs Ridge across multiple DVs and segments simultaneously, then counts how often each IV appears as a top driver — producing a frequency ranking of cross-cutting drivers.

---

## Prerequisites

```
pip install pandas numpy scipy scikit-learn openpyxl
```

### Required Inputs

| Input | Source | Description |
|-------|--------|-------------|
| Mapped data file | CSV/Excel | Survey data with IV and DV columns |
| IV variable list | Config/mapping | Attitude or motivation battery variables |
| DV variable list | Config/mapping | Behavioral or interest outcome variables |
| Segment variable | Config | Column for within-segment analysis |

---

## When to Use Each Approach

- **Ridge regression** (`run_ridge_regression`): Use when you have many correlated IVs (attitude batteries). Default alpha=0.1 works for most survey data. Preferred over OLS when IVs > 15.
- **Logistic regression** (`run_logistic_regression`): Use when the DV is binary (e.g., "purchased" vs "didn't purchase").
- **Multi-DV driver analysis** (`run_multi_dv_driver_analysis`): Use when you have many DVs and want to find cross-cutting drivers. Runs Ridge per DV per segment, then counts how often each IV appears as a top-N driver.

---

## Step-by-Step Workflow

### Step 1: Prepare Weighted Scores (if applicable)

When IVs interact (e.g., interest x spend priority):

```python
from survey_analysis_toolkit import create_weighted_scores

df, weighted_vars = create_weighted_scores(
    df,
    interest_vars=interest_var_list,      # e.g., [f'Q10r{i}' for i in range(1, 34)]
    spend_vars=spend_var_list,            # e.g., [f'Q10_SPENDr{i}' for i in range(1, 34)]
    interest_threshold=4,
    spend_score_map={1: 1, 4: 1, 2: 2, 3: 3},
)
```

### Step 2: Run Multi-DV Driver Analysis

```python
from survey_analysis_toolkit import run_multi_dv_driver_analysis

results = run_multi_dv_driver_analysis(
    df,
    iv_vars=iv_var_list,                  # e.g., [f'Q5r{i}' for i in range(1, 38)]
    iv_labels=motivation_labels,
    dv_vars=weighted_vars,
    dv_labels=activity_labels,
    segment_var=config['segment_var'],
    segments=config['segment_labels'],
    alpha=0.1,
    top_n=10,
)
```

### Step 3: Build Behavioral Profile Overlay

```python
from survey_analysis_toolkit import build_behavioral_profile

profile = build_behavioral_profile(
    df,
    behavior_vars=behavior_var_list,      # e.g., [f'Q8r{i}' for i in range(1, 11)]
    behavior_labels=behavior_labels,
    segment_var=config['segment_var'],
    segments=config['segment_labels'],
    t2b_codes=[4, 5],
)
```

### Step 4: Write Excel Output

```python
from survey_analysis_toolkit import write_regression_excel

write_regression_excel(results, profile, motivation_labels, activity_labels,
                       'output/regression_results.xlsx')
```

---

## Function Reference

| Function | Parameters | Returns |
|----------|-----------|---------|
| `create_weighted_scores(df, interest_vars, spend_vars, interest_threshold, spend_score_map)` | DataFrame + var lists | (df, new_var_names) |
| `run_ridge_regression(df, iv_vars, dv_var, alpha)` | DataFrame + vars | dict: betas, R-squared, n |
| `run_logistic_regression(df, iv_vars, dv_var, C)` | DataFrame + vars | dict: coefficients, odds_ratios |
| `run_multi_dv_driver_analysis(df, iv_vars, iv_labels, dv_vars, dv_labels, segment_var, segments, alpha, top_n)` | Full spec | dict: per-segment results |
| `build_behavioral_profile(df, behavior_vars, behavior_labels, segment_var, segments, t2b_codes)` | Full spec | dict: means, %T2B, indices |
| `write_regression_excel(results, profile, iv_labels, dv_labels, output_path)` | Results + path | Output path |

---

## Interpretation Guide

- **Driver frequency count**: An IV that appears as a top-10 driver for 8 out of 12 DVs is a cross-cutting motivator. One that appears for only 1 DV is a niche driver.
- **Standardized betas**: Comparable across IVs. A beta of 0.25 means a 1 SD increase in the IV predicts a 0.25 SD increase in the DV.
- **Alpha selection**: Default 0.1 works for most survey data. Increase alpha (more regularization) if VIFs are very high or you have more IVs than respondents.
