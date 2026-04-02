# Concept Test Survey Generation — Agent Instructions

## Purpose

Generate a complete, analysis-ready concept test questionnaire. Concept tests evaluate new product or service ideas by exposing respondents to concept stimuli and measuring reactions, diagnostics, and purchase intent. The generated survey must be compatible with the analysis pipeline defined in `ANALYTIC_COMPATIBILITY.md`.

---

## Prerequisites

### Required Inputs

| Input | Source | Description |
|-------|--------|-------------|
| Category / industry | User-provided | e.g., "plant-based snacks", "fintech app" |
| Target audience | User-provided | e.g., "U.S. adults 18-44 who snack daily" |
| Study objective | User-provided | e.g., "Evaluate 3 new product concepts for market potential" |
| Number of concepts | User-provided | How many concepts will be tested |
| Design type | User-provided | monadic, sequential_monadic, or comparison |
| Concept descriptions | User-provided | The actual concept stimuli (text, image refs) |
| Planned analyses | User-provided or inferred | Which analysis types will run on the data |
| LOI target | User-provided (optional) | Survey length in minutes (default: 10-15 min) |

---

## Step-by-Step Workflow

### Step 1: Select Examples

```python
from survey_generation_toolkit import select_examples

matches = select_examples(
    category="plant-based snacks",
    audience="U.S. adults 18-44 who snack daily",
    objective="concept test for market potential",
    methodology="concept_test",
    top_n=3
)
```

### Step 2: Build Prompt

```python
from survey_generation_toolkit import build_generation_prompt

prompt = build_generation_prompt(
    examples=matches,
    category="plant-based snacks",
    audience="U.S. adults 18-44 who snack daily",
    objective="concept test for market potential",
    methodology="concept_test",
    planned_analyses=["crosstabs", "ridge_regression"],
    loi_target=12
)
```

### Step 3: Generate Questionnaire

### Step 4: Validate

```python
from survey_generation_toolkit import validate_survey

report = validate_survey(
    survey,
    planned_analyses=["crosstabs", "ridge_regression"],
    methodology="concept_test"
)
```

This runs structural validators + analysis validators + `validate_concept_test()`.

---

## Section Order (Standard Concept Test)

| Order | Section | Typical # Questions | Purpose |
|---|---|---|---|
| 1 | Screener | 3-5 | Category relevance, no bias |
| 2 | Pre-Exposure Attitudes | 5-10 | Baseline attitudes before seeing concept |
| 3 | Concept Exposure | 1 per concept | Stimulus presentation with forced-read |
| 4 | Immediate Reactions | 5-7 per concept | First impressions: appeal, intent, uniqueness |
| 5 | Concept Diagnostics | 8-12 per concept | Deeper evaluation battery |
| 6 | Concept Comparison | 2-3 (if multi-concept) | Forced preference, rank order |
| 7 | Purchase Intent | 2-3 | Final outcome measures |
| 8 | Demographics | 5-8 | Classification |

---

## Design Type Guidelines

### Monadic (1 concept per respondent)
- Cleanest measurement — no order effects
- Requires larger sample (separate cells per concept)
- Best for: final go/no-go decisions, normative benchmarking

### Sequential Monadic (2-3 concepts per respondent)
- Each respondent sees 2-3 concepts in randomized order
- Must specify rotation scheme in programming_logic
- Order effects possible — analyze first-shown vs. later-shown
- Best for: relative comparison with moderate sample

### Comparison (all concepts shown)
- All concepts shown side-by-side
- Only for small concept sets (2-3 max)
- Forced preference is primary outcome
- Best for: head-to-head competitive evaluation

---

## Diagnostic Battery Design

Standard concept test diagnostics (all on 5-point agreement scale):

| Dimension | Example Statement |
|---|---|
| Problem-solution fit | "This product solves a real problem I have" |
| Usage fit | "I can see myself using this regularly" |
| Differentiation | "This is different from anything else available" |
| Value | "The price seems fair for what you get" |
| Advocacy | "I would tell friends/family about this" |
| Clarity | "I understand exactly what this offers" |
| Lifestyle fit | "This fits my lifestyle" |
| Credibility | "I believe this product can deliver on its promises" |

These diagnostics serve as IVs for regression against purchase intent (DV).

---

## Common Pitfalls

| Pitfall | Why It Breaks | Fix |
|---|---|---|
| No forced-exposure confirmation | Can't verify respondent read concept | Add "Please confirm you have read" gate |
| Pre-exposure attitudes missing | No baseline for shift analysis | Always measure pre-exposure |
| Same scale for reaction and diagnostic | Can't distinguish initial vs. considered response | Use separate batteries |
| No rotation in sequential monadic | Order bias contaminates results | Randomize concept order per respondent |
| Too many diagnostics per concept | Fatigue in multi-concept designs | Cap at 8-10 per concept |
