# ADR-001: Assistant Context Contract

**Status:** Accepted
**Date:** 2026-04-02
**Ticket:** P00-01

## Context

Every assistant call across the platform (brief analysis, questionnaire generation,
mapping suggestions, table QA, analysis interpretation, reporting) needs a consistent
context packet so the LLM receives grounded, versioned inputs.

## Decision

Define `AssistantContext` as a Pydantic model in `packages/shared/assistant_context.py`.

Key design choices:

1. **Single schema, progressive population.** Fields are optional at the model level
   but enforced per-stage via `validate_for_stage()`. This avoids a proliferation of
   stage-specific context types while keeping strict guarantees at call sites.

2. **Explicit version field.** `schema_version` is required and validated on
   construction. This allows future migrations without silent breakage.

3. **Stage-gate requirements table.** `_STAGE_REQUIREMENTS` maps each `WorkflowStage`
   to the fields that must be non-null/non-empty. Adding a new stage or tightening
   requirements is a one-line change.

4. **Extensible `extra` dict.** Stage-specific or experimental fields can be passed
   without modifying the core schema.

## Schema version

Current: `1.0.0`

## Fields

| Field | Type | Required at stage |
|-------|------|-------------------|
| project_id | str | all |
| stage | WorkflowStage | all |
| methodology | Methodology | all |
| brief | BriefContext | questionnaire+ |
| selected_sections | list[str] | questionnaire+ |
| questionnaire_ref | QuestionnaireVersionRef | mapping+ |
| mapping_ref | MappingVersionRef | table_qa+ |
| run_metadata | RunMetadata | analysis+ |

## Consequences

- All assistant call sites must construct and validate an `AssistantContext` before invocation.
- Schema changes require a version bump and migration path.
- Contract tests enforce required fields, preventing regressions.
