# MaxDiff Bundle Evaluation & Degradation — Agent Instructions

## Purpose

Evaluate pre-defined message bundles on two dimensions — average message strength and audience reach — then test the resilience of top-performing bundles by sequentially removing their weakest messages.

This analysis answers three questions:
1. **Which bundle is best?** (Bundle Evaluation)
2. **Which messages carry the bundle?** (Per-item contribution)
3. **What happens if we shorten the message?** (Bundle Degradation)

**Depends on:** Completed HB estimation from `MAXDIFF_HB_ESTIMATION.md`. Uses the Individual Data tab.

---

## Prerequisites

```
pip install pandas numpy scipy openpyxl
```

### Required Inputs

| Input | Source | Description |
|-------|--------|-------------|
| HB output workbook | MAXDIFF_HB_ESTIMATION output | Must contain "Individual Data" tab |
| Raw survey data | Excel/CSV | For audience cut variables |
| Bundle definitions | Config | Which items form each bundle |

---

## When to Use This Analysis

**Bundle Evaluation:** When the study includes pre-defined message combinations (e.g., one message per domain) and you need to determine which combination performs best.

**Bundle Degradation:** When the client needs to know:
- Can we shorten from 4 messages to 3 or 2 without losing audience coverage?
- Which messages are essential vs. expendable?
- Is the bundle "top-heavy" (carried by 1-2 items) or "balanced" (all items contribute)?

---

## Config Schema

Add `'bundles'` to the maxdiff config:

```python
config['maxdiff']['bundles'] = [
    {
        'name': 'Bundle 1',
        'items': [5, 12, 19, 23],       # Item numbers (1-indexed)
        'labels': ['A4', 'B5', 'C8', 'D2'],
    },
    {
        'name': 'Bundle 2',
        'items': [4, 10, 20, 24],
        'labels': ['A3', 'B1', 'C12', 'D3'],
    },
    # ... more bundles
]

# Optional: how many top bundles to include in degradation analysis
config['maxdiff']['bundle_degradation_top_n'] = 3
```

---

## Step-by-Step Workflow

### Step 1: Load Data (Same as Head-to-Head)

```python
indiv = pd.read_excel(OUTPUT_PATH, sheet_name='Individual Data')
utilities = indiv[util_cols].values
LINEAR_SCALE = 100.0 / utilities.mean(axis=0).max()
linear_indexed = utilities * LINEAR_SCALE + 100

# Merge with raw data for cuts
merged = df.merge(linear_df, on='record', how='inner')
```

### Step 2: Compute Bundle Metrics

For each bundle within each audience cut, compute two metrics:

**Average Index Score:**
```python
# Mean of the bundle's item-level population means
item_means = bundle_scores.mean(axis=0)  # per-item avg across respondents
bundle_avg = item_means.mean()            # avg across items
```

**Reach:**
```python
# % of respondents where at least one bundle item > 100 (individual-level)
above_avg = bundle_scores > 100           # (n, bundle_size) boolean
reached = above_avg.any(axis=1)           # True if any item above avg
reach_pct = reached.mean() * 100
```

**Why individual-level reach matters:** A bundle might have strong population-average scores, but if those scores are driven by a subset of respondents, some audience members won't find any message in the bundle compelling. Reach captures this breadth of appeal.

### Step 3: Rank Bundles

Sort by Total average index score (descending). Reach is a secondary indicator.

```python
bundle_ranking = sorted(bundles,
    key=lambda b: bundle_results[b['name']]['Total']['bundle_avg_index'],
    reverse=True)
```

### Step 4: Compute Per-Item Contributions

Within each bundle, report each item's individual score and reach:

```python
per_item_reach = above_avg.mean(axis=0) * 100  # % where this item > 100
```

This shows which messages are driving the bundle and which are along for the ride.

### Step 5: Bundle Degradation (Top N)

For each top bundle, within each cut:

```python
# Rank items by mean utility within the cut (ascending = weakest first)
item_utils = bundle_stats['item_mean_utils']
sort_asc = np.argsort(item_utils)

# Remove lowest-performing item
items_minus1 = [items[i] for i in range(len(items)) if i != sort_asc[0]]
stats_minus1 = compute_bundle_stats(items_minus1, indices)

# Remove two lowest-performing items
items_minus2 = [items[i] for i in range(len(items)) if i not in sort_asc[:2]]
stats_minus2 = compute_bundle_stats(items_minus2, indices)
```

**Key detail:** Items are ranked within each cut independently. The weakest item in the Total population may not be the weakest in a specific subgroup.

### Step 6: Write Excel Output

Two tabs:

**Bundle Evaluation tab:**
- Summary section: bundles ranked, Avg Index + Reach% per cut (2 columns per cut)
- Per-item detail section (Total only): each item's score and reach within its bundle

**Bundle Degradation tab:**
- One section per top bundle
- Three rows per bundle: Full (4 items), Remove 1 (3 items), Remove 2 (2 items)
- Delta rows showing change from full bundle
- All metrics shown across all 9 cuts

---

## Excel Output Formatting

### Bundle Evaluation Tab

| Element | Style |
|---------|-------|
| Bundle rank column | Navy data font, centered |
| Bundle name | Bold dark gray |
| Items list | Standard gray |
| Avg Index values | Navy data font |
| Reach % values | Navy data font, "0.0" number format |
| Per-item detail section | Separated by section header with medium border |

### Bundle Degradation Tab

| Element | Style |
|---------|-------|
| Section headers | "#{rank}: {name} ({items})" — navy bold, section border |
| Full bundle row | Zebra fill |
| Remove-1 row | White fill |
| Remove-2 row | Zebra fill |
| Delta rows | Italic gray, "+/-" prefix on values, "pp" suffix on reach |

---

## Interpretation Guide

### Bundle Evaluation

- **High avg + high reach = strong bundle.** The messages are individually strong and collectively appeal to nearly everyone.
- **Moderate avg + high reach:** The bundle has breadth but no standout messages. Useful for broad audiences.
- **High avg + lower reach:** The bundle has strong messages that appeal to most but not all respondents. Check which subgroups are missed.
- **Bundles sharing items:** When top bundles share 2-3 items (e.g., C8 + D2), those shared items are the "engine." The differentiating items are less critical.

### Bundle Degradation

- **Avg score increases when items removed:** This is expected when removed items were below the bundle average. It does NOT mean the bundle is better with fewer items — it means the removed items diluted the average.
- **Reach barely changes (< 1pp):** The remaining items are strong enough to cover the audience on their own. The bundle is "resilient" or "top-heavy."
- **Reach drops significantly (> 3pp):** The removed items were providing incremental coverage to respondents not reached by the remaining items. The bundle is "fragile" or "balanced."
- **Same degradation pattern across two bundles:** They likely share the same core items (e.g., Bundles 1 and 5 both degrade to C8 + D2).

### Strategic Implications

- A "top-heavy" bundle is safe for abbreviated communications — the core 2 items carry the weight.
- A "balanced" bundle requires the full message set for maximum coverage — shortening it means losing audience.
- If the client can only deliver 2 messages, identify the highest-reach 2-item core across all bundles.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| All bundles show 100% reach | Normal when bundles contain at least one dominant item. Look at per-item reach to differentiate |
| Avg index is below 100 for a bundle | The bundle's messages are collectively below average. Flag this to the client |
| Same items removed across all cuts | The within-bundle ranking is consistent across audiences — a good sign |
| Different items removed per cut | Report which items are cut-sensitive. This is a segmentation insight |
| Degradation shows 0.0pp reach change for both removals | The bundle has one dominant item that provides near-universal reach regardless of what else is included |
