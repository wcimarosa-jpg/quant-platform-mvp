# Message Test Survey Generation — Agent Instructions

## Purpose

Generate a complete, analysis-ready message testing questionnaire. Message tests evaluate communication materials (ads, claims, taglines, educational content) by measuring comprehension, believability, relevance, motivation, and persuasive impact. The generated survey must be compatible with the analysis pipeline defined in `ANALYTIC_COMPATIBILITY.md`.

---

## Prerequisites

### Required Inputs

| Input | Source | Description |
|-------|--------|-------------|
| Category / industry | User-provided | e.g., "pharma patient education", "brand advertising" |
| Target audience | User-provided | e.g., "Adults diagnosed with Type 2 diabetes" |
| Study objective | User-provided | e.g., "Identify most motivating message for treatment adherence" |
| Number of messages | User-provided | How many messages will be tested |
| Exposure design | User-provided | monadic, sequential_rotated, or full_battery |
| Message stimuli | User-provided | The actual message text or descriptions |
| Planned analyses | User-provided or inferred | Which analysis types will run on the data |
| LOI target | User-provided (optional) | Survey length in minutes (default: 10-15 min) |

---

## Step-by-Step Workflow

### Step 1: Select Examples

```python
from survey_generation_toolkit import select_examples

matches = select_examples(
    category="pharma patient education",
    audience="Adults diagnosed with Type 2 diabetes",
    objective="message testing for treatment adherence",
    methodology="message_test",
    top_n=3
)
```

### Step 2: Build Prompt

```python
from survey_generation_toolkit import build_generation_prompt

prompt = build_generation_prompt(
    examples=matches,
    category="pharma patient education",
    audience="Adults diagnosed with Type 2 diabetes",
    objective="message testing for treatment adherence",
    methodology="message_test",
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
    methodology="message_test"
)
```

This runs structural validators + analysis validators + `validate_message_test()`.

---

## Section Order (Standard Message Test)

| Order | Section | Typical # Questions | Purpose |
|---|---|---|---|
| 1 | Screener | 3-5 | Target audience qualification |
| 2 | Pre-Message Attitudes | 5-8 | Baseline awareness, attitudes, current behavior |
| 3 | Message Exposure | 1 per message | Controlled stimulus presentation |
| 4 | Message Diagnostics | 6-10 per message | Evaluation on standard dimensions |
| 5 | Message Comparison | 2-3 (if multi-message) | Forced preference, rank order |
| 6 | Outcome Intention | 2-3 | Behavioral intent after exposure |
| 7 | Demographics | 5-8 | Classification |

---

## Exposure Design Guidelines

### Monadic (1 message per respondent)
- Cleanest measurement, no carryover effects
- Requires separate sample cells per message
- Best for: detailed message optimization, regulatory claims testing

### Sequential Rotated (2-4 messages per respondent)
- Each respondent sees 2-4 messages in randomized order
- Must define rotation scheme in programming_logic
- Include order-of-exposure as a variable for analysis
- Best for: relative message comparison with moderate sample

### Full Battery (all messages shown)
- Only for small message sets (3-4 max)
- All shown sequentially with rotation
- Best for: quick directional read with limited sample

---

## Message Diagnostic Dimensions

Standard diagnostic battery (5-point agreement scale):

| Dimension | Example Statement |
|---|---|
| Clarity | "This message is easy to understand" |
| Believability | "I believe the claims in this message" |
| Relevance | "This message is relevant to me personally" |
| Motivation | "This message motivates me to take action" |
| Uniqueness | "This message tells me something new" |
| Emotional resonance | "This message made me feel something" |
| Main message recall | "What is the main point of this message?" (open-end) |
| Tone appropriateness | "The tone of this message feels right for the topic" |

These diagnostics serve as IVs for regression against outcome intention (DV).

---

## Pre/Post Shift Analysis

To measure message impact on attitudes:
1. Ask key attitude items in the pre-message section (e.g., "I believe treatment X is effective")
2. Re-ask the same items in the outcome section after all message exposure
3. The shift (post minus pre) measures message persuasive effect
4. Design identical question wording and scale for both measurements

---

## Common Pitfalls

| Pitfall | Why It Breaks | Fix |
|---|---|---|
| No pre-message baseline | Can't measure attitude shift | Always include pre-exposure measures |
| Missing forced-exposure check | Can't verify respondent read message | Add confirmation gate |
| Same diagnostic for very different message types | Poor construct validity | Adapt diagnostics to message content |
| No rotation in sequential design | Order bias contaminates results | Randomize message order |
| Too many diagnostics per message | Fatigue in multi-message designs | Cap at 6-8 per message |
| No open-end for main message recall | Can't verify comprehension | Include at least one recall open-end |
