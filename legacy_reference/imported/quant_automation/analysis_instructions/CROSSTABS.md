# Cross-Tabulation & Data Tables — Agent Instructions

## Purpose

Generate frequency tables, Top-2-Box summaries, multi-select tables, and segment crosstabs with significance testing and index scores. This is the standard quantitative deliverable for survey analysis.

---

## Prerequisites

```
pip install pandas numpy scipy openpyxl
```

### Required Inputs

| Input | Source | Description |
|-------|--------|-------------|
| Mapped data file | CSV/Excel | Survey data with variable columns |
| Project config | Config dict | Section plan, variable labels, scale definitions, segment variable |

---

## Config Requirements

The config must include:
- `data_path` — path to data file
- `segment_var` — column name for the segmentation/banner variable
- `segment_labels` — `{value: 'Label', ...}` mapping
- `sections` — ordered list of section definitions (see Table Types below)
- `scale_definitions` (optional) — reusable scale labels and T2B codes

---

## Table Types

| Type | Required Keys | Description |
|------|---------------|-------------|
| `segment_size` | — | Shows n and % for total and each segment |
| `single_select` | `var`, `label`, `value_labels` | Frequency distribution of a single variable |
| `multi_select` | `var_prefix`, `label`, `item_labels` | % selected for each item (coded 1=selected) |
| `t2b_summary` | `var_prefix`, `label`, `item_labels`, `t2b_codes` | Top-2-box % for rating batteries |
| `themed_net` | `label`, `themes`, `t2b_codes` | Average T2B across themed groups of items |
| `mean` | `var`, `label` | Mean and optional SD |
| `mean_battery` | `item_labels`, `label` | Mean for each item in a battery |
| `binary` | `var`, `label`, `true_label`, `false_label` | Binary variable as two rows |
| `derived_group` | `var`, `label`, `categories` | Derived categorical variable |

### Section Definition Example

```python
{
    'number': 1,
    'title': 'Demographics',
    'tables': [
        {'type': 'single_select', 'var': 'QD1', 'label': 'Gender',
         'value_labels': {1: 'Male', 2: 'Female'}},
        {'type': 'multi_select', 'var_prefix': 'QB2', 'label': 'Sources',
         'item_labels': {'QB2r1': 'Instagram', 'QB2r2': 'TikTok'}},
        {'type': 't2b_summary', 'var_prefix': 'QA1', 'label': 'Motivations',
         'item_labels': {'QA1r1': 'Statement 1', ...}, 't2b_codes': [4, 5]},
    ],
}
```

---

## Step-by-Step Workflow

### Step 1: Create Derived Variables (if needed)

```python
from survey_analysis_toolkit import create_derived_variables
df = pd.read_csv(config['data_path'], low_memory=False)
df = create_derived_variables(df, config)
```

### Step 2: Generate Full Data Tables

```python
from survey_analysis_toolkit import generate_full_data_tables
generate_full_data_tables(config, 'output/full_tables.xlsx')
```

### Step 3: Generate Segment Crosstabs

```python
from survey_analysis_toolkit import generate_segment_crosstabs
generate_segment_crosstabs(config, 'output/segment_crosstabs.xlsx',
                           include_significance=True, include_index=True)
```

---

## Function Reference

| Function | Parameters | Returns |
|----------|-----------|---------|
| `freq_table(df, var, labels)` | DataFrame, variable, labels | DataFrame |
| `multi_select_table(df, var_prefix, labels)` | DataFrame, prefix, labels | DataFrame |
| `grid_table(df, item_labels, scale_labels, t2b_codes)` | DataFrame + scale info | DataFrame |
| `mean_table(df, var)` | DataFrame, variable | DataFrame |
| `generate_full_data_tables(config, output_path, style_kit)` | Config + path | Output path |
| `generate_segment_crosstabs(config, output_path, include_significance, include_index)` | Config + path + flags | Output path |
| `calc_index(seg_val, total_val)` | Two values | Index = (seg/total) x 100 |
| `calc_proportion_ztest(p1, n1, p2, n2, alpha)` | Proportions + bases | bool |
| `get_sig_letters(values, bases, alpha)` | Arrays + alpha | Letter assignments |

---

## Scale-Specific T2B Thresholds

Different scales use different T2B definitions:
- **5-point agreement**: T2B = codes 4, 5 (Somewhat/Strongly agree)
- **4-point interest**: T2B = code 4 only (Very interested)
- **5-point frequency**: T2B = codes 4, 5 (Often/Very often)
- **4-point likelihood**: T2B = codes 3, 4 (Somewhat/Very likely)

Set `t2b_codes` in each table spec accordingly.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| String-coded numerics | `pd.to_numeric(df[var].replace(' ', pd.NA), errors='coerce')` |
| Missing columns | Toolkit skips silently. Check cross-reference output |
| Empty batteries (all NaN) | Filter: `{k: v for k, v in item_labels.items() if k in df.columns and df[k].notna().any()}` |
| Multi-page question prefixes | Include all page-prefixed column names in `item_labels` dict |
