# Attitude & Usage (A&U) Survey Generation — Agent Instructions

## Purpose

Generate a complete, analysis-ready Attitude & Usage questionnaire. A&U studies measure brand health, category dynamics, and consumer behavior patterns. The generated survey must be compatible with the analysis pipeline defined in `ANALYTIC_COMPATIBILITY.md`.

---

## Prerequisites

### Required Inputs

| Input | Source | Description |
|-------|--------|-------------|
| Category / industry | User-provided | e.g., "premium coffee", "streaming services" |
| Target audience | User-provided | e.g., "U.S. adults 25-54 who drink coffee weekly" |
| Study objective | User-provided | e.g., "Baseline brand health tracking for competitive positioning" |
| Brand list | User-provided | Brands to include in awareness/perception grids |
| Tracking type | User-provided or inferred | baseline, tracking_wave, or one_time |
| Planned analyses | User-provided or inferred | Which analysis types will run on the data |
| LOI target | User-provided (optional) | Survey length in minutes (default: 15-20 min) |

---

## Step-by-Step Workflow

### Step 1: Select Relevant Examples

```python
from survey_generation_toolkit import select_examples

matches = select_examples(
    category="premium coffee",
    audience="U.S. adults 25-54 who drink coffee weekly",
    objective="brand health tracking",
    methodology="attitude_usage",
    top_n=3
)
```

### Step 2: Build Prompt

A&U studies do not use behavioral/attitudinal framework selection — section guidance is provided directly from the registry.

```python
from survey_generation_toolkit import build_generation_prompt

prompt = build_generation_prompt(
    examples=matches,
    category="premium coffee",
    audience="U.S. adults 25-54 who drink coffee weekly",
    objective="brand health tracking",
    methodology="attitude_usage",
    planned_analyses=["crosstabs", "ridge_regression"],
    loi_target=18
)
```

### Step 3: Generate the Questionnaire

Use the assembled prompt to generate the questionnaire structure following the standard survey dict schema.

### Step 4: Validate

```python
from survey_generation_toolkit import validate_survey

report = validate_survey(
    survey,
    planned_analyses=["crosstabs", "ridge_regression"],
    methodology="attitude_usage"
)
```

This runs structural validators + analysis validators + `validate_brand_awareness()`.

### Step 5: Present to User

---

## Section Order (Standard A&U)

| Order | Section | Typical # Questions | Purpose |
|---|---|---|---|
| 1 | Screener | 3-5 | Qualify category purchasers/users |
| 2 | Demographics | 5-8 | Classification (placed early for quota management) |
| 3 | Category Usage & Behavior | 5-10 | Purchase frequency, brands used, channels |
| 4 | Brand Awareness | 3-5 | Unaided → Aided → Trial → Usage → Primary brand |
| 5 | Brand Perceptions Grid | 1-3 grids (8-15 attributes) | Brand × Attribute matrix |
| 6 | Attitudes & Motivations | 10-20 statements | Category attitudes (lighter than segmentation) |
| 7 | Media & Touchpoints | 3-5 | Information sources, channel influence |
| 8 | Outcomes (NPS, Satisfaction) | 3-5 | DVs for regression analysis |

**LOI guidance:** 15-20 minutes. Brand grids consume the most time — limit to brands respondent is aware of.

---

## Brand Awareness Design Rules

The brand awareness funnel is the defining section of an A&U study. Follow this standard sequence:

1. **Unaided awareness** — open-end: "What brands of [category] can you think of?"
2. **Aided awareness** — multi-select from the full brand list: "Which have you heard of?"
3. **Brand trial** — multi-select from aided list: "Which have you ever tried?"
4. **Past-period usage** — multi-select: "Which have you used in the past 3 months?"
5. **Most often used / preferred** — single-select

**Critical rule:** All aided questions must use the SAME brand list for consistency. Display logic should filter subsequent questions to only show brands the respondent is aware of.

---

## Brand Perceptions Grid Design

- **Rows:** 8-15 brand attributes (balanced across functional, emotional, social dimensions)
- **Columns:** brands from the aided awareness list (filtered to heard-of brands)
- **Scale options:** "Describes completely/well/somewhat/not very well/not at all" (5-point) or binary "Yes/No"
- **Display logic:** Only show brands respondent indicated in aided awareness

---

## Tracking Considerations

For tracking_wave studies:
- Maintain identical question wording from baseline wave
- Do not add/remove questions between waves
- Brand list updates require careful documentation
- New brands can be added to the aided list but not removed
- Attribute list should remain stable for trend analysis

---

## Common Pitfalls

| Pitfall | Why It Breaks | Fix |
|---|---|---|
| Inconsistent brand lists across sections | Can't link awareness to perceptions | Use ONE master brand list throughout |
| No unaided awareness before aided | Order bias inflates aided scores | Always ask unaided FIRST |
| Too many brands in perception grid | Respondent fatigue, poor data quality | Cap at 8-10 brands per grid, use display logic |
| Missing NPS or satisfaction DV | No regression outcome targets | Include standard outcome battery |
| Changing wording between tracking waves | Breaks trend comparability | Lock wording after baseline |
