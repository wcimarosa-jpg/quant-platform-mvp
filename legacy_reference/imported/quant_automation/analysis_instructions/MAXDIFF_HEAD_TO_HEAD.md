# MaxDiff Head-to-Head Paired Variant Comparisons — Agent Instructions

## Purpose

Compare paired message variants (a/b versions of the same concept) head-to-head using individual-level MaxDiff preference scores. Identifies which framing wins within each audience cut and whether the difference is statistically significant.

**Depends on:** Completed HB estimation from `MAXDIFF_HB_ESTIMATION.md`. Uses the Individual Data tab (per-respondent utilities) from the HB output workbook.

---

## Prerequisites

```
pip install pandas numpy scipy openpyxl
```

### Required Inputs

| Input | Source | Description |
|-------|--------|-------------|
| HB output workbook | MAXDIFF_HB_ESTIMATION output | Must contain "Individual Data" tab with per-respondent utilities |
| Raw survey data | Excel/CSV | For audience cut variables (segment, subgroup columns) |
| Paired variant definitions | Config | Which item numbers form a/b pairs |

---

## When to Use This Analysis

Use head-to-head comparisons when:
- The study tested **two or more framings of the same concept** (e.g., emotional vs rational language, short vs long copy)
- Both variants were included in the same MaxDiff exercise (not separate cells)
- You want to know which framing wins **within the same respondent** (paired comparison, not independent groups)

Do NOT use this when:
- Variants were tested in separate sample cells (use independent-samples t-test instead)
- You want to compare unrelated messages (that's what the standard indexed scores do)

---

## Config Schema

Add a `'paired_variants'` key to the maxdiff config:

```python
config['maxdiff']['paired_variants'] = [
    {
        'code': 'A2',
        'theme': 'Daily Life Impact',
        'a': 2,                             # Item number (1-indexed) for variant a
        'a_label': 'Emotional framing',
        'b': 3,                             # Item number (1-indexed) for variant b
        'b_label': 'Rational framing',
    },
    {
        'code': 'A5',
        'theme': 'Efficacy',
        'a': 6,
        'a_label': 'Specific statistic',
        'b': 7,
        'b_label': 'Qualitative description',
    },
    # ... more pairs
]
```

Each pair must reference item numbers that exist in the MaxDiff design.

---

## Step-by-Step Workflow

### Step 1: Load HB Utilities and Compute Linear Indexed Scores

Read per-respondent utilities from the Individual Data tab. Do NOT re-run HB estimation.

```python
indiv = pd.read_excel(OUTPUT_PATH, sheet_name='Individual Data')
util_cols = [f'Utility_Item{j+1}' for j in range(N_ITEMS)]
utilities = indiv[util_cols].values  # (N, K)

# Compute linear indexed scores
pop_means = utilities.mean(axis=0)
LINEAR_SCALE = 100.0 / pop_means.max()
linear_indexed = utilities * LINEAR_SCALE + 100
```

### Step 2: Merge with Raw Survey Data

Link individual utilities back to the raw data for audience cut variables.

```python
linear_df = pd.DataFrame(linear_indexed,
                          columns=[f'LinIdx_Item{j+1}' for j in range(N_ITEMS)])
linear_df['record'] = indiv['Record'].values
merged = df.merge(linear_df, on='record', how='inner')
```

### Step 3: Define Audience Cuts

Same cut structure as HB estimation:

```python
CUTS = {
    'Total': merged.index.tolist(),
    'Segment A': merged[merged['segment_var'] == 1].index.tolist(),
    'Segment B': merged[merged['segment_var'] == 2].index.tolist(),
    # ... etc
}
```

### Step 4: Run Paired Comparisons

For each pair, within each cut:

```python
for pair in config['maxdiff']['paired_variants']:
    for cut_name, indices in CUTS.items():
        sub = merged.loc[indices]
        scores_a = sub[f"LinIdx_Item{pair['a']}"].values
        scores_b = sub[f"LinIdx_Item{pair['b']}"].values

        mean_a, mean_b = scores_a.mean(), scores_b.mean()
        diff = mean_a - mean_b

        # Paired t-test (same respondents evaluated both)
        d = scores_a - scores_b
        se_d = d.std(ddof=1) / np.sqrt(len(d))
        t_stat = diff / max(se_d, 1e-10)
        p_value = 2 * (1 - t_dist.cdf(abs(t_stat), df=len(d) - 1))
```

**Why paired t-test:** Both variants were in the same MaxDiff exercise, so every respondent has a score for both. The paired test accounts for within-respondent correlation and is more powerful than an independent-samples test.

### Step 5: Write Excel Output

The output tab ("Head-to-Head Pairs") contains:
- One section per pair with a section header showing the pair code and theme
- Row for variant a (scores per cut)
- Row for variant b (scores per cut)
- Difference row with significance markers (* p<0.05, ** p<0.01, *** p<0.001)
- Winner highlighted in green bold; loser in gray when significant

---

## Excel Output Formatting

| Element | Style |
|---------|-------|
| Section headers | Navy bold, medium gray bottom border |
| Winner score | Green bold (#006600) |
| Loser score (when sig) | Gray italic (#999999) |
| Non-significant scores | Standard navy |
| Difference row | Bold navy if significant, italic gray if not |
| Significance markers | Appended to difference value: "+6.1 ***" |

---

## Interpretation Guide

- **All pairs significant:** The study has strong statistical power. Report the winning variant with confidence.
- **Mixed results across cuts:** If variant a wins in some cuts and b wins in others, this is a segmentation finding — different audiences respond to different framings.
- **Small gap but significant:** With paired data on 300+ respondents, even small differences (5-10 points) can be significant. Note the practical magnitude alongside statistical significance.
- **Large gap (30+ points):** This is a decisive framing difference. The losing variant should not be used.

### Common Framing Patterns

From prior MaxDiff studies, these patterns recur:
- **Specific data > vague claims** when the numbers are strong
- **Broad claims > specific data** when the numbers are modest
- **Concrete examples > abstract descriptions**
- **Outcome-focused language > process-focused language**
- **Speed + durability narratives > comparison-only claims**

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Merge produces fewer respondents than expected | Check that `record` column names match across files (case-sensitive) |
| All p-values = 0.0000 | Normal for large samples with clear preference differences. Report as p<0.001 |
| Scores for both variants below 100 | Both framings are below-average messages. The pair comparison still identifies the better framing, but note that neither is a strong message overall |
| Different winners across cuts | Report as a segmentation finding, not an error |
