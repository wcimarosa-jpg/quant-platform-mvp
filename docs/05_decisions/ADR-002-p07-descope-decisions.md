# ADR-002: P07 Descope Decisions for MVP

**Status:** Accepted
**Date:** 2026-04-03
**Sprint:** P07 pre-work

## Context

Codex review of the remaining backlog identified two high-risk items
that could blow the sprint budget without proportional MVP value.

## Decisions

### 1. MaxDiff: Count-based scoring replaces HB MCMC estimation

**Descoped:** Hierarchical Bayes MCMC estimation for individual-level
MaxDiff utilities.

**Kept:** Count-based scoring (best/worst counts, rescaled 0-100 scores).

**Rationale:** HB estimation is research-grade MCMC that requires either
a custom sampler or PyMC dependency. Count-based scoring covers ~80% of
practical MaxDiff use cases and is deterministic, fast, and fully testable.
HB can be added post-MVP as an optional upgrade.

### 2. Logistic regression deferred from Drivers suite

**Descoped:** `run_logistic_regression()` for binary DVs.

**Kept:** Ridge regression, Pearson correlations, weighted-effects analysis.

**Rationale:** Logistic regression is only needed when the DV is binary
(e.g., "purchased vs didn't purchase"), which is a minority case in
segmentation and A&U studies. Ridge + Pearson + weighted-effects covers
the core driver story. Adding logistic post-MVP requires minimal
integration work since the pattern will already exist.

### 3. P08-01 split recommended (not yet actioned)

**Recommendation:** Split insight copilot into evidence-retrieval
infrastructure (P08-01a) and LLM narrative generation (P08-01b).
To be decided when P08 starts.

## Consequences

- `result_schemas.py` defines `MaxDiffTURFResultSummary` with count-based
  fields only (no individual-level utilities).
- `DriversResultSummary` omits logistic-specific fields.
- Both schemas are extensible — adding HB or logistic post-MVP is additive.
