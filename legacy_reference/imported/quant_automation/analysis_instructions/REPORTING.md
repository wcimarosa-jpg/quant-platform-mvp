# Narrative Report Generation — Agent Instructions

## Purpose

Generate formatted Word documents (.docx) summarizing analysis results. The reporting system uses a **two-layer anti-hallucination architecture**:

1. **Findings extraction** (`findings.py`): Pure Python functions that consume analysis result dicts and produce structured finding objects with pre-built narrative sentences. Every number is placed by code.
2. **Document generation** (`reporting.py`): Template-based functions that arrange pre-built text into formatted Word documents. No numbers are computed or constructed at this layer.

This architecture ensures that **every number in a generated document originates from the analysis data** — the agent never writes numbers into prose.

---

## Prerequisites

```
pip install python-docx pandas numpy
```

---

## Supported Document Types

| Document Type | Extract Function | Generate Function | Input Source |
|---|---|---|---|
| MaxDiff item rankings | `extract_maxdiff_summary_findings` | `generate_maxdiff_summary_docx` | `compute_cut_statistics` output |
| Head-to-head pairs | `extract_h2h_findings` | `generate_h2h_summary_docx` | `compute_head_to_head` output |
| Bundle evaluation | `extract_bundle_findings` | `generate_bundle_summary_docx` | `compute_bundle_metrics` + `compute_bundle_degradation` |
| MaxDiff regression | `extract_maxdiff_regression_findings` | `generate_regression_summary_docx` | `run_maxdiff_regression` output |
| Multi-DV drivers | `extract_multi_dv_driver_findings` | `generate_multi_dv_driver_docx` | `run_multi_dv_driver_analysis` output |
| Segment profiles | `extract_segment_profile_findings` | `generate_segment_profile_docx` | `build_cluster_profiles` output |

---

## Quick Start: Convenience Wrapper

For the simplest workflow, use `generate_analysis_summary_docx` which calls extract + generate in one step:

```python
from survey_analysis_toolkit import generate_analysis_summary_docx

# MaxDiff summary
generate_analysis_summary_docx(
    'maxdiff_summary',
    (cut_stats, linear_cut_stats),  # tuple
    config,
    'output/maxdiff_summary.docx'
)

# Head-to-head
generate_analysis_summary_docx('h2h', h2h_results, config, 'output/h2h.docx')

# Bundles
generate_analysis_summary_docx(
    'bundles',
    (bundle_metrics, degradation_results),  # tuple
    config,
    'output/bundles.docx'
)

# Regression
generate_analysis_summary_docx(
    'maxdiff_regression', reg_results, config, 'output/regression.docx')

# Multi-DV drivers
generate_analysis_summary_docx(
    'multi_dv_drivers', driver_results, config, 'output/drivers.docx')

# Segment profiles
generate_analysis_summary_docx(
    'segment_profiles', profiles, config, 'output/segments.docx')
```

---

## Detailed Workflows

### 1. MaxDiff Item Rankings

**Prerequisites:** Completed HB estimation via `run_maxdiff_analysis`.

```python
from survey_analysis_toolkit import (
    extract_maxdiff_summary_findings,
    generate_maxdiff_summary_docx,
)

# results = run_maxdiff_analysis(config, output_path)
findings = extract_maxdiff_summary_findings(
    config,
    results['cut_stats'],
    results['linear_cut_stats'],
)
generate_maxdiff_summary_docx(findings, 'output/maxdiff_summary.docx')
```

**Document contents:** Title, tier summary, top/bottom items table with scores and vs-average, tier classification, per-cut breakdowns.

### 2. Head-to-Head Paired Comparisons

**Prerequisites:** Completed HB estimation. Config must have `config['maxdiff']['paired_variants']`.

```python
from survey_analysis_toolkit import (
    compute_head_to_head,
    extract_h2h_findings,
    generate_h2h_summary_docx,
    compute_linear_index,
    build_cuts,
)

# After HB estimation:
lin_indexed, _ = compute_linear_index(utilities)
cuts = build_cuts(resp_meta, config)
h2h_results = compute_head_to_head(config, lin_indexed, cuts)

findings = extract_h2h_findings(config, h2h_results)
generate_h2h_summary_docx(findings, 'output/h2h_comparisons.docx')
```

**Document contents:** Summary count of significant winners, pair-by-pair sections with winner/loser scores, difference magnitude and significance, per-cut breakdown tables, auto-detected strategic implications.

### 3. Bundle Evaluation & Degradation

**Prerequisites:** Completed HB estimation. Config must have `config['maxdiff']['bundles']`.

```python
from survey_analysis_toolkit import (
    compute_bundle_metrics,
    compute_bundle_degradation,
    extract_bundle_findings,
    generate_bundle_summary_docx,
)

bundle_metrics = compute_bundle_metrics(config, lin_indexed, cuts)
degradation = compute_bundle_degradation(config, lin_indexed, cuts, top_n=3)

findings = extract_bundle_findings(config, bundle_metrics, degradation)
generate_bundle_summary_docx(findings, 'output/bundle_evaluation.docx')
```

**Document contents:** Ranked bundle table (avg index + reach), per-bundle detail with item contributions, per-cut metrics, degradation analysis showing impact of removing weakest items, resilience assessment, strategic takeaways.

### 4. MaxDiff Key Driver Regression

**Prerequisites:** Completed MaxDiff analysis with regression enabled.

```python
from survey_analysis_toolkit import (
    extract_maxdiff_regression_findings,
    generate_regression_summary_docx,
)

# results = run_maxdiff_analysis(config, output_path, include_regression=True)
findings = extract_maxdiff_regression_findings(config, results['reg_results'])
generate_regression_summary_docx(findings, 'output/maxdiff_regression.docx')
```

**Document contents:** Per-cut sections with model fit (R-squared), top-5 drivers with standardized betas and significance, narrative bullets.

### 5. Multi-DV Driver Analysis

**Prerequisites:** Completed multi-DV Ridge regression via `run_multi_dv_driver_analysis`.

```python
from survey_analysis_toolkit import (
    extract_multi_dv_driver_findings,
    generate_multi_dv_driver_docx,
)

# driver_results = run_multi_dv_driver_analysis(df, iv_vars, ...)
findings = extract_multi_dv_driver_findings(config, driver_results)
generate_multi_dv_driver_docx(findings, 'output/multi_dv_drivers.docx')
```

**Document contents:** Cross-cutting drivers table (motivations that appear as top-5 across multiple segments), per-segment master driver rankings with frequency and effect size.

### 6. Segment Profiles

**Prerequisites:** Completed K-Means clustering and `build_cluster_profiles`.

```python
from survey_analysis_toolkit import (
    extract_segment_profile_findings,
    generate_segment_profile_docx,
)

# profiles = build_cluster_profiles(df, cluster_labels, profile_vars, ...)
findings = extract_segment_profile_findings(config, profiles)
generate_segment_profile_docx(findings, 'output/segment_profiles.docx')
```

**Document contents:** Overview table, per-segment pages with auto-generated summary, over-indexed attributes (index > 115) and under-indexed attributes (index < 85) with index scores.

---

## Legacy: Manual Segment Profiles

The original `generate_segment_summary_docx` function is still available for manually constructed profile dicts. Use `generate_segment_profile_docx` (from findings extraction) when possible — it eliminates the risk of mistyped numbers.

```python
from survey_analysis_toolkit import generate_segment_summary_docx

# Requires manually constructed segment_profiles list
generate_segment_summary_docx(config, segment_profiles, 'output/report.docx')
```

---

## Function Reference

| Function | Parameters | Returns |
|---|---|---|
| `extract_maxdiff_summary_findings(config, cut_stats, linear_cut_stats)` | Config + stats | Findings dict |
| `extract_h2h_findings(config, h2h_results)` | Config + H2H results | Findings dict |
| `extract_bundle_findings(config, bundle_metrics, degradation)` | Config + bundle data | Findings dict |
| `extract_maxdiff_regression_findings(config, reg_results)` | Config + regression | Findings dict |
| `extract_multi_dv_driver_findings(config, driver_results)` | Config + driver data | Findings dict |
| `extract_segment_profile_findings(config, profiles)` | Config + profiles | Findings dict |
| `generate_maxdiff_summary_docx(findings, output_path, title)` | Findings + path | Output path |
| `generate_h2h_summary_docx(findings, output_path, title)` | Findings + path | Output path |
| `generate_bundle_summary_docx(findings, output_path, title)` | Findings + path | Output path |
| `generate_regression_summary_docx(findings, output_path, title)` | Findings + path | Output path |
| `generate_multi_dv_driver_docx(findings, output_path, title)` | Findings + path | Output path |
| `generate_segment_profile_docx(findings, output_path, title)` | Findings + path | Output path |
| `generate_analysis_summary_docx(analysis_type, results, config, path)` | Type + data | Output path |
| `generate_segment_summary_docx(config, profiles, path, title)` | Legacy manual | Output path |
