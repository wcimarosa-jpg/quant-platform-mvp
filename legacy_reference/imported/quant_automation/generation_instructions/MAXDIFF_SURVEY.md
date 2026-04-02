# Standalone MaxDiff Survey Generation — Agent Instructions

## Purpose

Generate a complete, analysis-ready standalone MaxDiff questionnaire. In a standalone MaxDiff study, the best-worst scaling exercise is the centerpiece — not embedded within a larger segmentation or A&U study. The generated survey must be compatible with the analysis pipeline defined in `ANALYTIC_COMPATIBILITY.md`.

---

## Prerequisites

### Required Inputs

| Input | Source | Description |
|-------|--------|-------------|
| Category / industry | User-provided | e.g., "pharmaceutical messaging", "feature prioritization" |
| Target audience | User-provided | e.g., "HCPs who prescribe in [therapeutic area]" |
| Study objective | User-provided | e.g., "Prioritize 20 messages for campaign development" |
| MaxDiff dimension | User-provided | What respondents evaluate: appeal, importance, relevance |
| Item list | User-provided | The 15-30 items to be evaluated |
| Planned analyses | User-provided or inferred | maxdiff, maxdiff_regression, crosstabs |
| LOI target | User-provided (optional) | Survey length in minutes (default: 12-18 min) |

---

## Step-by-Step Workflow

### Step 1: Select Examples

```python
from survey_generation_toolkit import select_examples

matches = select_examples(
    category="pharmaceutical messaging",
    audience="HCPs who prescribe in oncology",
    objective="message prioritization",
    methodology="maxdiff",
    top_n=3
)
```

### Step 2: Build Prompt

```python
from survey_generation_toolkit import build_generation_prompt

prompt = build_generation_prompt(
    examples=matches,
    category="pharmaceutical messaging",
    audience="HCPs who prescribe in oncology",
    objective="message prioritization",
    methodology="maxdiff",
    planned_analyses=["maxdiff", "maxdiff_regression", "crosstabs"],
    loi_target=15
)
```

### Step 3: Generate Questionnaire

### Step 4: Validate

```python
from survey_generation_toolkit import validate_survey

report = validate_survey(
    survey,
    planned_analyses=["maxdiff", "maxdiff_regression", "crosstabs"],
    methodology="maxdiff"
)
```

---

## Section Order (Standalone MaxDiff)

| Order | Section | Typical # Questions | Purpose |
|---|---|---|---|
| 1 | Screener | 3-5 | Qualify for meaningful evaluation |
| 2 | Context & Warm-up | 3-5 | Orient respondent, establish evaluation frame |
| 3 | MaxDiff Exercise | 12-15 tasks | Core best-worst scaling |
| 4 | Motivation Rating | 1 battery (matching items) | Stated preference comparison |
| 5 | Outcome Variable | 1-3 | DV for MaxDiff regression |
| 6 | Audience Classification | 3-5 | Cuts for subgroup analysis |
| 7 | Demographics | 5-8 | Standard classification |

---

## MaxDiff Exercise Design Rules

1. **Item count:** 15-30 items (typical: 20-25)
2. **Items per set:** 4 (standard) or 5 (for 25+ items)
3. **Tasks per respondent:** 12-15
4. **BIB balance:** Each item appears in equal number of tasks
5. **Item comparability:** ALL items must be evaluable on the same dimension
6. **Item length:** Keep items similar in length (15-30 words each)
7. **No overlap:** Items should not be subsets or near-duplicates of each other

### Head-to-Head Variant Pairs

If head-to-head analysis is planned, include a/b variant pairs:
- Same concept, two framings (emotional vs. rational, etc.)
- Both variants must appear in the BIB design
- Define pairs in the maxdiff_design block:
  ```
  paired_variants: [{code: 'A5', a: 5, b: 6, a_label: 'Emotional', b_label: 'Rational'}]
  ```

### Bundle Design

If bundle evaluation is planned, ensure items span logical groupings:
- Items from different benefit categories that could form a value proposition
- Define bundles post-design (not in the questionnaire structure)

---

## Motivation Rating Section

Re-present MaxDiff items as a rating battery:
- Same items, presented individually (not in sets)
- 5-point scale: "How motivating is this [message/feature]?"
- Enables stated (rating) vs. revealed (MaxDiff) preference comparison
- Serves as IVs for MaxDiff regression alongside MaxDiff utilities

---

## Audience Cuts

Define variables for subgroup analysis in the MaxDiff results:
- Pre-defined segment membership (if applicable)
- Key behavioral splits (e.g., heavy/light user, brand loyalist/switcher)
- Attitudinal clusters (if attitudinal items included)
- These become the "cuts" dimension in MaxDiff HB reporting

---

## Common Pitfalls

| Pitfall | Why It Breaks | Fix |
|---|---|---|
| Items not comparable on one dimension | Uninterpretable utilities | Ensure single evaluative dimension |
| Items vary wildly in length | Visual bias toward shorter items | Edit to similar length (15-30 words) |
| Overlapping items | Suppresses both items' utilities | Ensure each tests a distinct concept |
| No context before MaxDiff | Respondents lack evaluation frame | Add warm-up section |
| Missing outcome DV | Can't run MaxDiff regression | Include behavioral intent question |
| No audience cuts defined | Can't analyze subgroup differences | Include classification variables |
