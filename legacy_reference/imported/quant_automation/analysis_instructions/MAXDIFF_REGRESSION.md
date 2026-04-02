# MaxDiff Key Driver Regression — Agent Instructions

## Purpose

Run key driver regression linking message preference to a behavioral outcome (e.g., purchase intent, prescribing likelihood, recommendation). Supports two parallel models — stated motivation ratings and revealed MaxDiff preference scores — to identify which messages drive behavior from both stated and revealed perspectives.

**Depends on:** Completed HB estimation from `MAXDIFF_HB_ESTIMATION.md`. Uses the Individual Data tab for MaxDiff scores and the raw survey data for motivation ratings and the dependent variable.

---

## Prerequisites

```
pip install pandas numpy scipy openpyxl
```

### Required Inputs

| Input | Source | Description |
|-------|--------|-------------|
| HB output workbook | MAXDIFF_HB_ESTIMATION output | "Individual Data" tab with per-respondent utilities |
| Raw survey data | Excel/CSV | DV column (e.g., purchase intent) and IV columns (e.g., message motivation ratings) |
| Regression config | Config | DV/IV specifications, cut definitions |

---

## When to Use This Analysis

- You have a **behavioral outcome** (purchase intent, prescribing likelihood, recommendation, satisfaction) alongside the MaxDiff exercise
- You have **stated motivation ratings** for the same messages tested in the MaxDiff (e.g., "how motivating is this message?" on a 1-5 scale)
- You want to compare **stated drivers** (what respondents say motivates them) vs **revealed drivers** (what they actually prefer when forced to choose)

### Single-Model vs Two-Model Approach

- **Single model (motivation ratings only):** Use when no MaxDiff data is available, or when the MaxDiff items don't map 1:1 to motivation ratings.
- **Single model (MaxDiff only):** Use when no motivation ratings are available.
- **Two-model comparison (recommended):** Use when both are available. Messages significant in both models are the strongest strategic recommendations.

---

## Config Schema

```python
config['maxdiff']['regression'] = {
    'dv_col': 'outcome_var',
    'dv_label': 'Behavioral outcome (1-5)',

    # Model A: Stated motivation ratings
    'motivation_iv_cols': [f'motivation_r{i}' for i in range(1, 26)],
    'motivation_label': 'Message Motivation Rating (1-5)',

    # Model B: Linear MaxDiff indexed scores (computed from HB utilities)
    'use_maxdiff_ivs': True,  # Will auto-compute from Individual Data tab

    # Output configuration
    'output_tabs': 'all',  # 'combined', 'standalone', or 'all' (both)
}
```

---

## Step-by-Step Workflow

### Step 1: Load and Merge Data

```python
# Raw survey data
df = pd.read_excel(DATA_PATH, sheet_name=config.get('sheet_name'))

# HB utilities from Individual Data tab
indiv = pd.read_excel(OUTPUT_PATH, sheet_name='Individual Data')
utilities = indiv[util_cols].values

# Compute linear indexed scores
LINEAR_SCALE = 100.0 / utilities.mean(axis=0).max()
linear_indexed = utilities * LINEAR_SCALE + 100

# Merge on record
linear_df = pd.DataFrame(linear_indexed, columns=[f'LinMD_Item{j+1}' for j in range(N_ITEMS)])
linear_df['record'] = indiv['Record'].values
merged = df.merge(linear_df, on='record', how='inner')
```

### Step 2: Run OLS with Z-Scored Standardization

For each model within each cut:

```python
def run_standardized_regression(y_raw, X_raw):
    """OLS on z-scored variables -> standardized betas, p-values, R-squared, VIFs."""
    n, p = X_raw.shape

    # Z-score all variables
    y = (y_raw - y_raw.mean()) / max(y_raw.std(ddof=1), 1e-10)
    X = (X_raw - X_raw.mean(axis=0)) / np.maximum(X_raw.std(axis=0, ddof=1), 1e-10)

    # OLS with intercept
    X_int = np.column_stack([np.ones(n), X])
    betas = np.linalg.inv(X_int.T @ X_int) @ (X_int.T @ y)

    # Standard errors, t-tests, p-values
    residuals = y - X_int @ betas
    SSR = np.sum(residuals ** 2)
    mse = SSR / max(n - p - 1, 1)
    se = np.sqrt(np.diag(np.linalg.inv(X_int.T @ X_int) * mse))
    t_stats = betas[1:] / np.maximum(se[1:], 1e-10)
    p_values = 2 * (1 - t_dist.cdf(np.abs(t_stats), df=max(n - p - 1, 1)))

    # R-squared
    SST = np.sum((y - y.mean()) ** 2)
    r_sq = 1 - SSR / SST if SST > 0 else 0

    # VIFs for multicollinearity check
    vifs = [...]  # 1 / (1 - R^2_j) for each IV regressed on all others

    return {'betas': betas[1:], 'p_values': p_values, 'r_squared': r_sq, 'vifs': vifs, 'n': n}
```

**Why z-scored standardization:** Standardized betas are comparable across IVs with different scales (1-5 ratings vs indexed scores in the 50-200 range). A beta of 0.3 means: a 1 SD increase in this IV predicts a 0.3 SD increase in the DV.

**Why OLS (not Ridge):** With ~25 IVs and 300+ respondents, OLS is appropriate. Ridge would be preferred with 50+ IVs or severe multicollinearity (VIFs > 10).

### Step 3: Run Both Models Across All Cuts

```python
# 2 models x N cuts
for cut_name, indices in CUTS.items():
    sub = merged.loc[indices]
    y = sub[DV_COL].values.astype(float)

    # Model A: Motivation ratings
    X_motivation = sub[MOTIVATION_IV_COLS].values.astype(float)
    motivation_results[cut_name] = run_standardized_regression(y, X_motivation)

    # Model B: Linear MaxDiff scores
    X_md = sub[MD_IV_COLS].values.astype(float)
    md_results[cut_name] = run_standardized_regression(y, X_md)
```

### Step 4: Sort Messages

```python
# Combined tab: sort by average |beta| across both models (Total)
avg_abs_beta = (np.abs(motivation_results['Total']['betas']) +
                np.abs(md_results['Total']['betas'])) / 2
combined_sort = np.argsort(-avg_abs_beta)

# Standalone tabs: sort by own |Total beta|
motivation_sort = np.argsort(-np.abs(motivation_results['Total']['betas']))
md_sort = np.argsort(-np.abs(md_results['Total']['betas']))
```

### Step 5: Write Excel Output

Three tabs (when `output_tabs='all'`):

**Regression - Combined:**
- Side-by-side motivation beta and MaxDiff beta per cut (2 columns per cut)
- Merged cut name headers spanning both columns
- Separate R-squared rows for each model
- Sorted by average |Total beta| across both models

**Regression - Motivation Ratings (standalone):**
- Single Std. Beta column per cut
- R-squared and Adj. R-squared shown
- Sorted by own |Total beta|

**Regression - MaxDiff Scores (standalone):**
- Same layout as motivation standalone
- Sorted by own |Total beta|

---

## Excel Output Formatting

| Element | Style |
|---------|-------|
| Significant beta (p<0.05) | Bold navy |
| Non-significant beta | Italic gray |
| Beta values | "0.000" number format |
| R-squared rows | Italic gray sample-size font |
| Sort indicator | Noted in subtitle text |

---

## Interpretation Guide

### Comparing the Two Models

- **Message significant in both models:** Strongest recommendation. The message both motivates respondents (stated) and is preferred in trade-offs (revealed).
- **Significant in motivation only:** Respondents say it motivates them, but it doesn't stand out when forced to choose. May reflect social desirability or top-of-mind awareness rather than true preference.
- **Significant in MaxDiff only:** Respondents prefer it when forced to trade off, but don't rate it as especially motivating in isolation. May be undervalued — worth investigating further.
- **Significant in neither:** Not a driver of the outcome from either perspective.

### R-Squared Comparison

- Motivation model R-squared is typically higher than MaxDiff model R-squared because motivation ratings are on the same stated scale as the outcome (both are "what respondents say").
- MaxDiff R-squared reflects a harder test — linking revealed preference from forced trade-offs to stated behavioral intent.
- Small sample cuts (n<50) will have inflated R-squared. Focus interpretation on cuts with n>75.

### VIF Check

- VIFs > 5: Note multicollinearity. Betas are less stable but overall model fit is fine.
- VIFs > 10: Severe multicollinearity. Consider dropping highly correlated IVs or switching to Ridge.
- MaxDiff model typically has lower VIFs than motivation ratings because MaxDiff forces differentiation.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Very few significant betas | Normal with 25 IVs competing. Focus on the combined ranking, not individual p-values |
| Negative R-squared on small cuts | Too few respondents for the number of IVs. Skip cuts with n < 50 |
| Motivation columns have missing values | Use `sub[IV_COLS].fillna(sub[IV_COLS].mean())` or drop incomplete rows |
| Linear indexed scores are all identical for an item | That item has zero variance in utilities — likely a BIB design issue |
| Merge produces 0 matches | Check record column name and type (int vs string) |
