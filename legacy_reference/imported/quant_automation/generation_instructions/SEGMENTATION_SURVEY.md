# Segmentation Survey Generation — Agent Instructions

## Purpose

Generate a complete, analysis-ready segmentation questionnaire using few-shot learning from annotated exemplars. The generated survey must be compatible with the analysis pipeline defined in `ANALYTIC_COMPATIBILITY.md`.

---

## Prerequisites

```
pip install python-docx
```

### Required Inputs

| Input | Source | Description |
|-------|--------|-------------|
| Category / industry | User-provided | e.g., "premium pet food", "streaming media" |
| Target audience | User-provided | e.g., "U.S. adults 25-54 who own dogs" |
| Study objective | User-provided | e.g., "Identify actionable segments for brand positioning" |
| Planned analyses | User-provided or inferred | Which analysis types will run on the data |
| Budget / LOI target | User-provided (optional) | Survey length in minutes (default: 15-20 min) |

---

## Step-by-Step Workflow

### Step 1: Select Relevant Examples

Call `example_selector.select_examples()` with the user's category, audience, and objective.

```python
from survey_generation_toolkit import select_examples

matches = select_examples(
    category="premium pet food",
    audience="U.S. adults 25-54 who own dogs",
    objective="segmentation for brand positioning",
    top_n=3
)
```

This returns the 2-3 most relevant annotated exemplars ranked by:
1. Category similarity (exact match > adjacent category > different)
2. Framework compatibility (same behavioral/attitudinal type)
3. Annotation quality rating (A+ > A > B+)
4. Structural similarity (people vs. occasion vs. hybrid segmentation)

### Step 2: Select Frameworks

Based on the user's category and study objective, select one behavioral framework and one attitudinal framework. Use the matching logic:

**Behavioral Framework Selection:**

| If the category involves... | Use framework |
|---|---|
| Traditional purchase path (CPG, retail) | Purchase Funnel |
| Progressive engagement (media, subscription) | Engagement Journey |
| Context-driven usage (food, beverage, wellness) | Occasion-Based |
| Non-linear behaviors (donations, cultural, identity) | Thematic Categories |
| Simple / exploratory | No Framework |

**Attitudinal Framework Selection:**

| If the study focuses on... | Use framework |
|---|---|
| Understanding "why" / jobs-to-be-done | Motivational Drivers |
| Universal human needs | Maslow's Hierarchy |
| Identity, culture, values-driven | Identity & Values |
| Brand positioning, competitive analysis | Brand Perceptions |
| Functional vs. emotional vs. social balance | Dimensional Model |
| Specialized category attitudes (health, sustainability) | Category-Specific |
| Exploratory / simple | No Framework |

### Step 3: Build Few-Shot Prompt

Call `prompt_builder.build_generation_prompt()` to assemble the LLM prompt with selected examples and framework guidance.

```python
from survey_generation_toolkit import build_generation_prompt

prompt = build_generation_prompt(
    examples=matches,
    behavioral_framework="purchase_funnel",
    attitudinal_framework="brand_perceptions",
    category="premium pet food",
    audience="U.S. adults 25-54 who own dogs",
    objective="segmentation for brand positioning",
    planned_analyses=["kmeans", "crosstabs", "ridge_regression", "maxdiff"],
    loi_target=18
)
```

### Step 4: Generate the Questionnaire

Use the assembled prompt to generate the questionnaire structure. The output should be a Python dict following this schema:

```python
survey = {
    'metadata': {
        'title': str,
        'category': str,
        'target_audience': str,
        'study_objective': str,
        'estimated_loi_minutes': int,
        'behavioral_framework': str,
        'attitudinal_framework': str,
    },
    'screener': [
        {
            'question_id': 'QS01',
            'question_text': str,
            'question_type': 'single_choice' | 'multiple_choice' | 'grid_single',
            'options': [{'code': int, 'label': str}],
            'programming_logic': {'terminate_if': str, 'skip_to': str},
            'design_rationale': str,
        },
    ],
    'sections': [
        {
            'section_number': int,
            'section_title': str,
            'section_type': 'demographics' | 'behavioral' | 'attitudinal' | 'maxdiff' | 'outcome',
            'questions': [
                {
                    'question_id': str,
                    'question_text': str,
                    'question_type': str,
                    'scale': str | None,  # reference to scale_definitions key
                    'options': [...] | None,
                    'items': [...] | None,  # for batteries
                    'var_prefix': str | None,
                    'design_rationale': str,
                },
            ],
        },
    ],
    'scale_definitions': {
        'agreement_5pt': {
            'labels': {1: 'Strongly Disagree', 2: 'Somewhat Disagree',
                       3: 'Neither Agree nor Disagree',
                       4: 'Somewhat Agree', 5: 'Strongly Agree'},
            't2b_codes': [4, 5],
        },
    },
    'maxdiff_design': {  # only if MaxDiff is planned
        'items': [{'code': str, 'text': str}],
        'n_items': int,
        'items_per_set': int,
        'n_tasks': int,
    },
    'analysis_config_hints': {
        'segment_var': str,  # suggested segment variable name
        'clustering_vars': [str],  # var IDs for K-Means input
        'iv_vars': [str],  # for regression IVs
        'dv_vars': [str],  # for regression DVs
    },
}
```

### Step 5: Validate

Call `survey_validator.validate_survey()` to check the generated questionnaire against analytic compatibility constraints.

```python
from survey_generation_toolkit import validate_survey

report = validate_survey(survey, planned_analyses=["kmeans", "crosstabs", "ridge_regression"])
if report['pass']:
    print("Survey passes all compatibility checks")
else:
    for issue in report['issues']:
        print(f"  FAIL: {issue}")
```

Fix any issues flagged by the validator before presenting the survey to the user.

### Step 6: Present to User

Present the generated questionnaire as a structured document. Include:
- Screener logic with termination points
- Section-by-section question listing with response codes
- Scale definitions
- Design rationale for key decisions (framework choice, battery sizing, etc.)
- LOI estimate breakdown by section
- Analysis compatibility confirmation

---

## Questionnaire Section Order (Standard)

A segmentation questionnaire typically follows this order:

| Order | Section | Typical # Questions | Purpose |
|---|---|---|---|
| 1 | Screener | 3–6 | Qualify respondents, set quotas |
| 2 | Category Behavior | 5–10 | Usage, purchase, engagement patterns |
| 3 | Attitudinal Battery | 20–35 statements | Clustering input (K-Means/VarClus) |
| 4 | MaxDiff Exercise | 12–15 tasks | Preference/importance measurement |
| 5 | Brand Perceptions | 5–10 (optional) | Competitive positioning |
| 6 | Behavioral Outcomes | 3–5 | DVs for regression (intent, loyalty, etc.) |
| 7 | Demographics | 5–8 | Classification, profiling |

**LOI guidance:** 15–20 minutes is standard. Attitudinal battery + MaxDiff consume ~60% of LOI.

---

## Attitudinal Battery Design Rules

The attitudinal battery is the most critical section — it feeds K-Means clustering, VarClus, and Ridge regression. Follow these rules:

1. **Size:** 20–35 statements. Fewer than 15 is insufficient for clustering. More than 40 causes respondent fatigue.

2. **Scale consistency:** All items on the same scale (5-point or 7-point agreement). Never mix scales within the battery.

3. **Dimensional coverage:** Statements should span 4–7 conceptual dimensions (e.g., for pet food: health consciousness, indulgence/premium attitudes, brand loyalty, price sensitivity, ingredient awareness, pet-as-family beliefs, convenience orientation).

4. **Polarity balance:** Target ~60% positively-framed, ~30% negatively-framed, ~10% neutral. Prevents acquiescence bias.

5. **Statement phrasing:**
   - First person: "I always check ingredient labels" (not "People who check labels...")
   - Specific: "I'm willing to pay $5+ more for organic ingredients" (not "Price matters to me")
   - Discriminating: Statements that different segments would answer differently
   - Avoid double-barrels: One idea per statement

6. **Directional coding:** Higher values = more agreement. Flag any reverse-coded items explicitly.

---

## MaxDiff Design Rules

If MaxDiff is a planned analysis:

1. **Item count:** 15–30 items (typical: 20–25)
2. **Items per set:** 4 (standard) or 5 (for large item sets)
3. **Tasks per respondent:** 12–15
4. **BIB balance:** Each item appears in equal number of sets
5. **Item comparability:** All items must be evaluable on the same dimension (e.g., "most appealing message" or "most important feature")
6. **Item length:** Keep items similar in length (15–30 words each)
7. **No overlap:** Items should not be subsets of each other

---

## Framework-Specific Behavioral Section Patterns

### Purchase Funnel
Questions should map to stages: Awareness → Consideration → Purchase → Usage → Loyalty
- Awareness: aided/unaided brand awareness, category familiarity
- Consideration: brand consideration set, information sources
- Purchase: channel, frequency, recency, basket composition
- Usage: occasions, consumption context, satisfaction
- Loyalty: repurchase intent, switching triggers, advocacy

### Engagement Journey
Questions should map to progressive engagement stages (custom per category):
- Discovery → Consumption → Active Participation → Community → Advocacy
- Each stage has its own behavioral indicators

### Occasion-Based
Questions should capture usage contexts:
- When (time of day, day of week, seasonality)
- Where (at home, at work, on-the-go, social settings)
- With whom (alone, family, friends, colleagues)
- Why (functional need, emotional state, social occasion)

### Thematic Categories
Questions organized by behavioral themes (custom per study):
- e.g., donation behaviors, cultural engagement, identity expression
- Each theme is a group of related behaviors, not a sequential journey

---

## Example Workflow

```python
# Full generation workflow
from survey_generation_toolkit import (
    select_examples,
    build_generation_prompt,
    validate_survey,
)

# 1. Find relevant annotated examples
examples = select_examples(
    category="premium pet food",
    audience="U.S. adults 25-54 who own dogs",
    objective="segmentation for brand positioning",
    top_n=3,
)

# 2. Build prompt with examples and framework guidance
prompt = build_generation_prompt(
    examples=examples,
    behavioral_framework="purchase_funnel",
    attitudinal_framework="dimensional_model",
    category="premium pet food",
    audience="U.S. adults 25-54 who own dogs",
    objective="segmentation for brand positioning",
    planned_analyses=["kmeans", "crosstabs", "ridge_regression"],
    loi_target=18,
)

# 3. Agent uses the prompt to generate the survey dict
survey = ...  # generated by the LLM using the assembled prompt

# 4. Validate against analytic constraints
report = validate_survey(survey, planned_analyses=["kmeans", "crosstabs", "ridge_regression"])
assert report['pass'], f"Validation failed: {report['issues']}"

# 5. Present to user
```

---

## Common Pitfalls

| Pitfall | Why It Breaks | Fix |
|---|---|---|
| Mixed scales in attitudinal battery | K-Means distance distortion | Use one scale throughout |
| Fewer than 15 attitude items | Insufficient variance for clustering | Add items spanning more dimensions |
| MaxDiff items that aren't comparable | Uninterpretable utilities | Ensure single evaluative dimension |
| Missing behavioral outcome DVs | Ridge regression has no targets | Add 3–5 outcome questions |
| Multi-select items not binary-coded | Cross-tab function errors | Design for 1/0 coding per item |
| No screener termination logic | Unqualified respondents in data | Define terminate_if rules |
| Acquiescence bias (all positive items) | Inflated agreement, weak clustering | Balance polarity 60/30/10 |
