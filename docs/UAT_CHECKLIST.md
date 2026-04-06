# UAT Checklist — MVP Release Readiness

**Generated:** 2026-04-06
**Test command:** `pytest tests/e2e/test_full_journey.py -v`

## Full Journey (TestFullJourney)

- [ ] Brief ingestion (docx/pdf/md) extracts all fields
- [ ] Preflight gate blocks incomplete briefs, passes complete ones
- [ ] Methodology + section selection works for all 8 methodologies
- [ ] Questionnaire generation produces valid output
- [ ] Validation engine passes generated questionnaires
- [ ] DOCX export produces valid Word document
- [ ] Decipher export produces valid JSON with schema checks
- [ ] Data upload + profiling works for CSV (row count, columns, missingness)
- [ ] Auto-mapping maps data columns to questionnaire variables
- [ ] Table generation computes real values from DataFrame
- [ ] Table QA checks pass on clean data
- [ ] Analysis run completes (drivers/segmentation/maxdiff_turf)
- [ ] Schema validation passes on analysis results
- [ ] Insight evidence extraction produces trace-linked items
- [ ] Narrative generation produces zero unsupported claims
- [ ] All artifacts saved to disk (DOCX, manifest, QA report)

## Failure Paths (TestFailurePaths)

- [ ] Incomplete brief blocks generation (preflight fails)
- [ ] Empty data file rejected
- [ ] Missing analysis column produces actionable error
- [ ] Bad questionnaire (missing response codes) fails validation
- [ ] Comparing non-completed runs raises error
- [ ] Unsupported file format rejected

## Methodology Coverage (TestUATChecklist)

For each of the 8 methodologies:

| Methodology | Generates | Validates | Exports DOCX |
|-------------|-----------|-----------|-------------|
| Segmentation | [ ] | [ ] | [ ] |
| Attitude & Usage | [ ] | [ ] | [ ] |
| Drivers | [ ] | [ ] | [ ] |
| Concept Monadic | [ ] | [ ] | [ ] |
| Creative Monadic | [ ] | [ ] | [ ] |
| Brand Equity Tracker | [ ] | [ ] | [ ] |
| MaxDiff | [ ] | [ ] | [ ] |
| TURF | [ ] | [ ] | [ ] |

## Analysis E2E

- [ ] Drivers: data → ridge → Pearson → weighted-effects → insight → narrative
- [ ] Segmentation: data → VarClus → KMeans → profiles → insight → narrative
- [ ] MaxDiff+TURF: data → scoring → reach → insight → narrative

## Run Comparison

- [ ] Version diffs detected
- [ ] Metric deltas computed
- [ ] Causal explanations generated for significant changes

## Pass Criteria

- All automated tests pass (`pytest tests/e2e/ -v`)
- Zero unsupported claims in any narrative
- All 8 methodologies generate + validate + export
- All 3 analysis types complete end-to-end
- All failure paths produce actionable errors (not crashes)
