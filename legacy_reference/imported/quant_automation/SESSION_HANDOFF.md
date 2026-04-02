# Session Handoff — Multi-Methodology Survey Generation Platform

**Date:** 2026-02-23
**Status:** Multi-methodology refactor COMPLETE

---

## What Has Been Built (All Complete)

### Phase 1: Foundation (Prior Sessions)

1. **Annotation File Reorganization** — 4 canonical JSONs, 12 reference QREs, clean folder structure
2. **ANALYTIC_COMPATIBILITY.md** — Maps every analysis type to questionnaire design constraints
3. **SEGMENTATION_SURVEY.md** — Step-by-step segmentation generation workflow
4. **Python Toolkit (v1)** — example_selector, prompt_builder, survey_validator for segmentation
5. **AGENT_INSTRUCTIONS.md (v1)** — Segmentation-only agent guide

### Phase 2: Multi-Methodology Refactor (This Session — COMPLETE)

6. **methodology_registry.py** (NEW) — Central registry defining all 7 methodologies:
   - `segmentation` — K-Means clustering + MaxDiff + regression
   - `attitude_usage` — Brand health tracking with awareness funnels
   - `concept_test` — Monadic/sequential concept evaluation
   - `maxdiff` — Standalone best-worst scaling
   - `message_test` — Communication evaluation with diagnostics
   - `pricing` — Van Westendorp PSM + Gabor-Granger
   - `innovation` — Feature prioritization + whitespace exploration

   Each methodology defines: label, instruction_file, default_analyses, study_type_field/values, methodology_validators, section_order, frameworks (segmentation only), section_guidance.

7. **example_selector.py** (REFACTORED) — Added `methodology` parameter, replaced `_get_seg_type()` with `_get_study_type()`, framework matching now pulls from registry via `get_framework_keywords()`. Backward compatible (`methodology="segmentation"` default).

8. **prompt_builder.py** (REFACTORED) — Removed hardcoded `_BEHAVIORAL_GUIDANCE` and `_ATTITUDINAL_GUIDANCE` dicts. Now pulls guidance from registry. Added `methodology` parameter. Generates section order, framework guidance (if applicable), and section design guidance from the registry. Backward compatible.

9. **survey_validator.py** (REFACTORED) — Added 5 new methodology-specific validators:
   - `validate_brand_awareness()` — unaided/aided awareness sequence
   - `validate_concept_test()` — concept exposure + diagnostics exist
   - `validate_message_test()` — message exposure + diagnostic battery
   - `validate_pricing()` — pricing exercise + product exposure
   - `validate_innovation()` — current state + feature exposure/MaxDiff

   `validate_survey()` now accepts `methodology` parameter and auto-runs the methodology's validators from the registry. Backward compatible.

10. **6 New Instruction Files** (NEW):
    - `ATTITUDE_USAGE_SURVEY.md` — Brand awareness funnels, perception grids, tracking considerations
    - `CONCEPT_TEST_SURVEY.md` — Monadic/sequential design, diagnostic battery, pre/post measurement
    - `MAXDIFF_SURVEY.md` — Standalone MaxDiff, H2H variants, bundles, motivation rating
    - `MESSAGE_TEST_SURVEY.md` — Exposure designs, diagnostic dimensions, pre/post shift
    - `PRICING_SURVEY.md` — Van Westendorp 4-question sequence, Gabor-Granger ladder, logical constraints
    - `INNOVATION_SURVEY.md` — Pain points, feature MaxDiff, innovation attitudes, scope guidelines

11. **__init__.py** (UPDATED) — 22 exports total covering all 4 modules

12. **AGENT_INSTRUCTIONS.md** (REWRITTEN) — Covers all 7 methodologies, updated module reference with new signatures, methodology selection guide, decision guide

---

## Architecture Summary

### Two-tier design: shared foundation + methodology registry

```
methodology_registry.py ← Single source of truth for all 7 methodologies
        ↓
example_selector.py  ← Reads framework keywords from registry
prompt_builder.py    ← Reads guidance text from registry
survey_validator.py  ← Reads validator names from registry
```

**Design decisions made:**
- Registry structure: dict of dicts in a single file (simple, flat, easy to read)
- Framework guidance lives IN the registry (not separate files)
- Only segmentation has behavioral/attitudinal framework selection; all others use section_guidance
- All functions default to `methodology="segmentation"` for backward compatibility
- Methodology-specific validators are dispatched by name from the registry

### Validator Tiers

| Tier | When Run | Examples |
|---|---|---|
| Structural | Always | screener, variable_naming, scale_definitions |
| Analysis-specific | Based on planned_analyses | crosstabs, clustering, maxdiff, regression |
| Methodology-specific | Based on methodology | brand_awareness, concept_test, message_test, pricing, innovation |

---

## File Inventory (Current State)

```
Pipeline/
├── Analysis Files/
│   ├── analysis_instructions/          (9 .md files)
│   ├── survey_analysis_toolkit/        (8+ .py + AGENT_INSTRUCTIONS.md)
│   └── example_configs/                (3 files)
│
├── Survey Generation Files/
│   ├── annotations/                    (4 canonical JSONs)
│   │   ├── nfl_fan_segmentation.json
│   │   ├── pfizer_segmentation.json
│   │   ├── grillos_pickles.json
│   │   └── ala_donor_segmentation.json
│   ├── reference_questionnaires/       (12 .docx QREs)
│   ├── annotation_templates/           (v3 worksheet .docx)
│   ├── generation_instructions/
│   │   ├── ANALYTIC_COMPATIBILITY.md
│   │   ├── SEGMENTATION_SURVEY.md
│   │   ├── ATTITUDE_USAGE_SURVEY.md     ← NEW
│   │   ├── CONCEPT_TEST_SURVEY.md       ← NEW
│   │   ├── MAXDIFF_SURVEY.md            ← NEW
│   │   ├── MESSAGE_TEST_SURVEY.md       ← NEW
│   │   ├── PRICING_SURVEY.md            ← NEW
│   │   └── INNOVATION_SURVEY.md         ← NEW
│   ├── survey_generation_toolkit/
│   │   ├── __init__.py                  ← UPDATED (22 exports)
│   │   ├── methodology_registry.py      ← NEW (central registry)
│   │   ├── example_selector.py          ← REFACTORED (methodology param)
│   │   ├── prompt_builder.py            ← REFACTORED (registry-driven)
│   │   ├── survey_validator.py          ← REFACTORED (5 new validators)
│   │   └── AGENT_INSTRUCTIONS.md        ← REWRITTEN (all 7 methodologies)
│   └── archive/
│
└── SESSION_HANDOFF.md                   (THIS FILE)
```

---

## Open Items / Future Work

1. **Annotations for non-segmentation methodologies** — Current 4 annotations are all segmentation. The example selector falls back to best category/audience match. Adding A&U, concept test, or other methodology annotations would improve few-shot quality.

2. **End-to-end testing** — Generate a survey for each methodology and validate to confirm the full pipeline works. Each methodology's instruction file includes a complete workflow example.

3. **SEGMENTATION_SURVEY.md update** — Could be updated to reference the registry pattern instead of hardcoded framework tables, but it still works as-is since the Python code handles the abstraction.
