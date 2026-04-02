# MaxDiff HB Estimation — Agent Instructions

## Purpose

Run a Hierarchical Bayes MaxDiff (best-worst scaling) analysis: extract choice data from a mapped survey, estimate individual-level utilities via MCMC, compute indexed preference scores, generate audience cut statistics with significance testing, and write formatted Excel output.

This is the **core MaxDiff pipeline**. Other MaxDiff analyses (head-to-head, bundle evaluation, regression) build on the outputs produced here.

---

## Prerequisites

```
pip install pandas numpy scipy openpyxl
```

### Required Inputs

| Input | Source | Description |
|-------|--------|-------------|
| Raw survey data | Excel/CSV | The mapped data file with MaxDiff choice columns |
| BIB design | Config | Balanced Incomplete Block sets defining which items appear together |
| Item codes & text | Config | Short codes (e.g., "A1") and full message text for all items |
| Audience cut definitions | Config | Filter logic for each audience segment |

---

## Config Schema

The config must have a top-level `'maxdiff'` key:

```python
config = {
    'data_path': 'data.xlsx',
    'sheet_name': 'Sheet1',
    'study_title': 'My MaxDiff Study',
    'maxdiff': {
        'design': {
            'n_items': 20,
            'items_per_set': 4,
            'n_tasks': 10,
            'canonical_sets': [
                [1, 2, 5, 11], [1, 3, 18, 20], ...
            ],
        },
        'item_codes': {1: 'A1', 2: 'A2', ...},
        'item_text': {1: 'Full message text...', ...},
        'column_schema': 'simple',  # or 'region_prefix'
        'meta_columns': ['record', 'respondent_id', 'segment_var'],
        'mcmc': {
            'n_iterations': 100000,
            'burn_in': 50000,
            'thin': 10,
            'seed': 42,
            'target_accept': (0.20, 0.40),
        },
        'cuts': [
            {'name': 'Total', 'filter': {}},
            {'name': 'Segment A', 'filter': {'segment_var': 1}},
            {'name': 'Segment B', 'filter': {'segment_var': 2}},
            {'name': 'High Interest', 'filter': {'interest_var': [4, 5]}},
        ],
        'comparison_pairs': [
            ('Segment A', 'Segment B', 'Segment'),
            ('High Interest', 'Low Interest', 'Interest Level'),
        ],
    },
}
```

### Column Schema Options

- **`region_prefix`**: Columns follow `QMD_{region}_coded_{t}best` / `QMD_{region}_coded_{t}worst` pattern. Region determined from a grouping variable. Use `region_prefix_config` to map group codes to region prefixes.
- **`simple`**: Columns follow `Best_{t}` / `Worst_{t}` pattern. Set `best_col_pattern` and `worst_col_pattern` in config.

### MCMC Parameters

| Key | Default | Description |
|-----|---------|-------------|
| `n_iterations` | 100000 | Total MCMC iterations |
| `burn_in` | 50000 | Burn-in iterations to discard |
| `thin` | 10 | Thinning interval for stored draws |
| `seed` | 42 | Random seed for reproducibility |
| `target_accept` | (0.20, 0.40) | Target MH acceptance rate range |

---

## Step-by-Step Workflow

### Step 1: Extract Choice Data

Parse the raw survey data into the structured arrays needed for HB estimation.

```python
df = pd.read_excel(config['data_path'], sheet_name=config.get('sheet_name'))
choice_data = extract_maxdiff_choices(df, config)
# Returns: (resp_meta, best_items, best_choice, worst_items, worst_choice)
```

Each respondent's choice tasks are encoded as:
- `best_items[i, t, :]` — the item indices (0-based) shown in task t
- `best_choice[i, t]` — position of the item chosen as best
- `worst_items[i, t, :]` — the remaining items after best is removed
- `worst_choice[i, t]` — position of the item chosen as worst

### Step 2: Run HB Estimation

```python
utilities = hb_estimate(choice_data, config)
# Returns: ndarray (N, K) posterior mean utilities, zero-centered per respondent
```

**What happens inside:**
1. Starting values from Best-Worst counts (scaled to [-2, 2])
2. Gibbs sampling with Sigma-oriented Metropolis-Hastings proposals
3. Conjugate Normal update for population mean (mu)
4. Inverse-Wishart update for population covariance (Sigma)
5. Adaptive proposal scaling during burn-in (target 25-35% acceptance)
6. Post-burn-in draws thinned and averaged for posterior means
7. Split-half R-hat diagnostic reported (target < 1.1)

**Runtime:** Scales roughly linearly with respondent count and iterations. Example: ~5 minutes for 300 respondents, 25 items, 100k iterations on a modern machine.

### Step 3: Compute Indexed Scores

Two indexing methods are available. **Use log-linear for most purposes.**

```python
# Exponential (softmax) — use for choice simulation only
exp_indexed = compute_exponential_index(utilities)

# Log-linear — use for strategic message prioritization
lin_indexed, scale_factor = compute_linear_index(utilities)
```

**Exponential**: `exp(u_i) / sum(exp(u_j)) * 100` per respondent, then rescaled so 100 = average. Winner-take-more behavior (Jensen's inequality). Items near the middle get compressed.

**Log-linear**: `utilities * scale + 100` where scale calibrates the top item's population mean to ~200. Proportional to raw log-odds. Differences are interpretable and proportional.

**When items disagree between methods** (e.g., index 111 linear vs 75 exponential): this happens when items cluster near the middle. The exponential method exaggerates small differences. Linear is recommended for strategic decisions.

### Step 4: Compute Cut Statistics

```python
cuts = build_cuts(choice_data[0], config)
cut_stats = compute_cut_statistics(lin_indexed, cuts, n_items=config['maxdiff']['design']['n_items'])
cross_sig = compute_cross_cut_significance(
    cut_stats, config['maxdiff']['comparison_pairs'],
    n_items=config['maxdiff']['design']['n_items']
)
```

For each cut:
- Mean indexed score per item
- Standard error per item
- Within-cut significance flags (item vs 100, two-tailed t-test, p<0.05)
- Significance thresholds (100 ± t_crit × avg_SE)

Cross-cut significance uses Welch's t-test with Satterthwaite degrees of freedom.

### Step 5: Write Excel Output

The standard output includes:
- **HB Comparison** — Exponential indexed scores, all cuts side-by-side, cross-cut significance
- **Linear Comparison** — Log-linear indexed scores, same layout
- **V1 Comparison** — Raw utilities, ranks, preference shares per cut
- **Individual cut tabs** (optional) — Per-cut detail with Utility, SE, Share
- **Individual Data** — Per-respondent utilities and indexed scores

All tabs use QA2 styling (navy/gray, Arial, zebra striping, significance formatting).

---

## Function Reference

### Data Preparation

| Function | Parameters | Returns |
|----------|-----------|---------|
| `parse_maxdiff_design(config)` | Config dict | `{'n_items', 'items_per_set', 'n_tasks', 'canonical_sets'}` |
| `extract_maxdiff_choices(df, config)` | DataFrame + config | `(resp_meta, best_items, best_choice, worst_items, worst_choice)` |

### HB Estimation

| Function | Parameters | Returns |
|----------|-----------|---------|
| `hb_estimate(choice_data, config)` | Choice data tuple + config | ndarray (N, K) posterior mean utilities |

### Indexing

| Function | Parameters | Returns |
|----------|-----------|---------|
| `compute_exponential_index(utilities)` | ndarray (N, K) | ndarray (N, K) indexed scores |
| `compute_linear_index(utilities)` | ndarray (N, K) | `(indexed, scale_factor)` |

### Cut Statistics

| Function | Parameters | Returns |
|----------|-----------|---------|
| `build_cuts(resp_meta, config)` | Metadata list + config | OrderedDict `{name: [indices]}` |
| `compute_cut_statistics(indexed, cuts, n_items)` | Indexed scores + cuts | dict per cut: means, SEs, sig flags |
| `compute_cross_cut_significance(cut_stats, pairs, n_items)` | Stats + pairs | dict `{(a,b): sig_flags}` |

### Orchestrator

| Function | Parameters | Returns |
|----------|-----------|---------|
| `run_maxdiff_analysis(config, output_path, include_cuts, include_turf, include_regression)` | Config + options | dict with all results + output path |

---

## Convergence Troubleshooting

| Symptom | Fix |
|---------|-----|
| R-hat > 1.2 | Increase `n_iterations` to 200k, `burn_in` to 100k |
| Acceptance rate < 15% | Reduce initial proposal scale or increase `target_accept` lower bound |
| Acceptance rate > 50% | Proposals are too small; increase proposal scale |
| Utility range very narrow (e.g., [-0.5, 0.5]) | Starting values may be poor; check BIB design extraction |
| Individual utilities all near zero | Check that best/worst columns are correctly parsed |

---

## Output Files

| Tab | Contents |
|-----|----------|
| Linear Comparison | Log-linear indexed scores, all cuts, cross-cut significance |
| HB Comparison | Exponential indexed scores, all cuts, cross-cut significance |
| V1 Comparison | Utility, Rank, Share% per cut |
| {Cut Name} (optional) | Per-cut detail: Rank, Code, Message, Avg Utility, SE, Avg Share, SE |
| Individual Data | Per-respondent: Record, meta columns, Utility per item, IndexedScore per item |
