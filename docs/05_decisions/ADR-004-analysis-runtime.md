# ADR-004: Analysis Runtime Architecture

**Status:** Accepted
**Date:** 2026-04-06
**Ticket:** P04-01, P07-01, P07-02

## Context

The platform supports multiple survey analysis methodologies (drivers, segmentation,
MaxDiff/TURF) that share common lifecycle patterns: validation, execution, result
schema enforcement, and insight generation. Each methodology needs to be independently
testable, pluggable, and composable (e.g., VarClus + KMeans as a composite).

## Decision

### Plugin-based analysis registry

- **`@register_analysis(name)`** decorator registers single-step analysis functions
  in a global registry (`packages/survey_analysis/run_orchestrator.py`)
- **`register_composite(name, steps)`** chains multiple analysis steps (e.g., VarClus
  dimensionality reduction followed by KMeans clustering)
- **`execute_run()`** manages the full lifecycle: queued → running → completed/failed

### Typed result schemas

- Each methodology has a Pydantic result schema (`DriversResultSummary`,
  `SegmentationResultSummary`, `MaxDiffTURFResultSummary`)
- `validate_result()` is wired into `execute_run()` — invalid results fail the run
- Schemas are additive (new fields can be added without breaking existing consumers)

### Job queue integration

- Heavy analyses run through the persistent job queue (`packages/shared/job_queue.py`)
  with retry, timeout enforcement, and dead-letter handling
- Idempotency keys prevent duplicate runs of the same analysis configuration

### Insight generation

- Split into two phases per Codex recommendation:
  - **Evidence retrieval** (`insight_evidence.py`): extracts statistical evidence with trace paths
  - **Narrative generation** (`insight_narrative.py`): deterministic templates at plain/analyst depth
- **Run comparison** (`run_comparison.py`): version diffs, metric deltas, causal explanations

## Alternatives Considered

| Alternative | Pros | Cons | Why not chosen |
|------------|------|------|----------------|
| Monolithic analyzer | Simple | Can't add methodologies independently | Violates open-closed principle |
| Celery task queue | Battle-tested | Heavy dependency, Redis required | Overkill for MVP scale |
| HB MCMC for MaxDiff | Research-grade accuracy | Complex dependency, slow | Descoped per ADR-002 |
| LLM-generated insights | More flexible narratives | Non-deterministic, expensive | Deterministic templates sufficient for MVP |

## Consequences

- Adding a new methodology requires: register function + result schema + tests
- Composite analyses reuse existing single-step functions
- All analysis results are typed and validated before storage
- Insight generation is decoupled from analysis execution

## References

- `packages/survey_analysis/run_orchestrator.py` — registry and lifecycle
- `packages/survey_analysis/drivers.py` — Ridge, Pearson, weighted-effects
- `packages/survey_analysis/segmentation.py` — VarClus + KMeans composite
- `packages/survey_analysis/maxdiff_turf.py` — count-based scoring + greedy TURF
- `packages/survey_analysis/result_schemas.py` — typed result models
- `packages/survey_analysis/insight_evidence.py` — evidence extraction
- `packages/survey_analysis/insight_narrative.py` — deterministic narratives
- ADR-002: P07 descope decisions (HB MCMC, logistic regression)
