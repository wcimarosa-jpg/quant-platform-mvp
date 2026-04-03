# Methodology Rigor Checklist

Use this checklist as a required quality gate for methodology-related tickets and analysis runs.

## Cross-Method (All Studies)

- [ ] Research objective and decision use-case documented.
- [ ] Population, inclusion/exclusion, and geography explicit.
- [ ] Sample source, quotas, and achieved sample sizes reported.
- [ ] Field dates and weighting approach documented.
- [ ] Missing-data handling rules fixed before analysis.
- [ ] Base sizes shown on all reported tables/charts.
- [ ] Statistical test type + alpha threshold pre-specified.
- [ ] Multiple-comparison handling documented (if applicable).
- [ ] Reproducibility metadata logged (run config, data hash, mapping version, questionnaire version).
- [ ] QA log includes flagged anomalies and resolution.

## Attitude & Usage (A&U)

- [ ] Awareness funnel structure present (unaided -> aided -> familiarity/usage).
- [ ] Category usage and brand usage windows clearly defined.
- [ ] Key batteries use consistent scales and anchors.
- [ ] Brand metrics are measured comparably across brands.
- [ ] Weighting/trend comparability rules documented.
- [ ] Output includes weighted and unweighted bases.

## Segmentation

- [ ] Segmentation battery has sufficient item count and conceptual breadth.
- [ ] Scale consistency enforced for clustering inputs.
- [ ] Preprocessing documented (standardization, reverse coding, outlier policy).
- [ ] Cluster candidate range tested (not single-k only).
- [ ] Cluster quality metrics reported (silhouette, Davies-Bouldin).
- [ ] Final cluster choice justified quantitatively + interpretability.
- [ ] Profiles include practical differentiators (behavior, attitudes, outcomes).
- [ ] Stability check performed (seed/split-sample sanity check).

## Drivers Analysis

- [ ] DV definition is explicit and business-relevant.
- [ ] IV candidates screened for data quality and low variance.
- [ ] Multicollinearity addressed (ridge + VIF diagnostics where useful).
- [ ] Modeling choices documented (standardization, CV/train-test if used).
- [ ] Pearson used descriptively, not as sole causal evidence.
- [ ] Weighted-effects method and normalization documented.
- [ ] Driver rankings include uncertainty context.
- [ ] Segment-level driver differences tested before claims.

## Concept Testing (Monadic)

- [ ] True monadic assignment (one concept per respondent).
- [ ] Random assignment and cell balance verified.
- [ ] Stimulus exposure controlled and consistent.
- [ ] Core diagnostic battery standardized across concepts.
- [ ] Order effects neutralized (if any non-monadic elements exist).
- [ ] Success thresholds pre-declared.
- [ ] Open-end coding rules documented if used.
- [ ] Recommendations tied to statistically defensible differences.

## Creative Testing (Monadic)

- [ ] One creative per respondent (or explicit rationale otherwise).
- [ ] Exposure context realistic and documented.
- [ ] Core metrics present (cut-through, clarity, brand linkage, persuasion).
- [ ] Data quality checks for speeders/straightliners applied.
- [ ] Creative comparisons adjusted for cell/base differences.
- [ ] Diagnostics include "why" layer (attribute/open-end support).
- [ ] Final ranking is not based on a single metric only.
- [ ] Recommendations include optimization direction.

## Brand Equity Tracker

- [ ] Wave-to-wave wording/scales locked for comparability.
- [ ] Core equity dimensions explicitly defined.
- [ ] Trend breaks documented (sample, weighting, questionnaire changes).
- [ ] Minimum sample per subgroup maintained.
- [ ] Weighting/rim rules stable or changes disclosed.
- [ ] Reporting distinguishes real movement vs noise.
- [ ] Driver linkage tested before attribution claims.
- [ ] Significant shifts include base/context notes.

## MaxDiff

- [ ] Item list is mutually exclusive, clear, and decision-relevant.
- [ ] Design balanced/connective (item frequency and pair coverage).
- [ ] Tasks/respondent and items/task within target range.
- [ ] Data quality checks on impossible patterns and speeders.
- [ ] Estimation settings documented and convergence checked.
- [ ] Utilities/indexing method documented and consistent.
- [ ] Segment/cut comparisons include significance handling.
- [ ] Interpretation avoids overclaiming tiny utility gaps.

## TURF

- [ ] Reach definition binary rule is explicit.
- [ ] Candidate universe and constraints documented.
- [ ] Unduplicated reach computed correctly.
- [ ] Marginal reach by added item reported.
- [ ] Sensitivity tested for threshold assumptions.
- [ ] Segment-level TURF performed where strategic.
- [ ] Recommended portfolio sizes provided (top-N scenarios).
- [ ] Tradeoffs documented (reach vs complexity/cost).

## Reporting / Insight Integrity

- [ ] Every numeric claim in narrative is traceable to computed output.
- [ ] Insight text distinguishes fact, inference, and recommendation.
- [ ] Uncertainty/limitations section included.
- [ ] No unsupported AI-only claims.
- [ ] Export package includes methodology appendix and QA summary.
