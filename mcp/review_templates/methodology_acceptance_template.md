# MCP Methodology Acceptance Template

Use this template in every methodology-related `review.request` and `review.post_feedback`.

## How To Use

1. Claude attaches a completed checklist section for the relevant methodology ticket.
2. Reviewer validates checklist evidence against code/tests/output artifacts.
3. Reviewer may only mark `approved` if:
   - all required checklist items are either checked or explicitly marked "N/A" with rationale,
   - supporting evidence is provided.

Reference checklist:

- [docs/02_analysis_specs/rigor_checklist.md](/c:/Users/Will%20Cimarosa/Documents/EggStrategy_Automation/quant-platform-mvp/docs/02_analysis_specs/rigor_checklist.md)

---

## Ticket Metadata

- Ticket ID:
- Methodology:
- Branch:
- Revision ID:
- Reviewer:

## Evidence Links

- Test results:
- Output artifacts:
- Run metadata/provenance:
- Relevant code paths:

## Cross-Method Gate (Required)

- [ ] Objective/use-case documented
- [ ] Population/filters documented
- [ ] Sample/quotas documented
- [ ] Missing-data rule documented
- [ ] Base sizes shown
- [ ] Statistical thresholds defined
- [ ] Reproducibility metadata logged

## Methodology-Specific Gate

### A&U
- [ ] Awareness funnel structure
- [ ] Usage windows defined
- [ ] Scale consistency
- [ ] Weighted/unweighted bases

### Segmentation
- [ ] Cluster range tested
- [ ] Silhouette and/or Davies-Bouldin reported
- [ ] Cluster selection rationale documented
- [ ] Stability check completed

### Drivers
- [ ] Ridge/logistic outputs
- [ ] Pearson outputs
- [ ] Weighted-effects outputs
- [ ] Multicollinearity handling documented

### Concept Monadic
- [ ] Random monadic assignment
- [ ] Balanced cells
- [ ] Standardized diagnostics
- [ ] Predefined success thresholds

### Creative Monadic
- [ ] One stimulus/respondent
- [ ] Core creative metrics present
- [ ] Quality filters applied
- [ ] Multi-metric winner logic

### Brand Equity Tracker
- [ ] Wave comparability protected
- [ ] Trend-break controls documented
- [ ] Shift significance/context documented

### MaxDiff
- [ ] Balanced/connective design
- [ ] Estimation/convergence checks
- [ ] Utility/index method documented

### TURF
- [ ] Reach rule explicit
- [ ] Unduplicated reach verified
- [ ] Marginal reach/diminishing returns reported

## Assistant Integrity Gate (AI-first required)

- [ ] Assistant responses grounded in project context packet
- [ ] No unsupported numeric narrative claims
- [ ] Explanations link to evidence artifacts
- [ ] User approval checkpoints honored

## Reviewer Decision

- Decision: `changes_requested` / `approved`
- Blocking findings (if any):
- Notes:
