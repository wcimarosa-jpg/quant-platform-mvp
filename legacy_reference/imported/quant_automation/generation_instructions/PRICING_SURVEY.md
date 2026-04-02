# Pricing Survey Generation — Agent Instructions

## Purpose

Generate a complete, analysis-ready pricing questionnaire using Van Westendorp Price Sensitivity Meter (PSM) and/or Gabor-Granger methodology. Pricing studies determine optimal price points, acceptable price ranges, and price elasticity. The generated survey must be compatible with the analysis pipeline defined in `ANALYTIC_COMPATIBILITY.md`.

---

## Prerequisites

### Required Inputs

| Input | Source | Description |
|-------|--------|-------------|
| Category / industry | User-provided | e.g., "premium skincare", "SaaS subscription" |
| Target audience | User-provided | e.g., "Women 25-54 who spend $50+/month on skincare" |
| Study objective | User-provided | e.g., "Determine optimal price range for new serum launch" |
| Product/concept description | User-provided | What is being priced (enough detail for evaluation) |
| Pricing method | User-provided | van_westendorp, gabor_granger, or both |
| Price range context | User-provided | Category price range for Gabor-Granger ladder |
| Planned analyses | User-provided or inferred | Typically crosstabs (specialized pricing analysis) |
| LOI target | User-provided (optional) | Survey length in minutes (default: 8-12 min) |

---

## Step-by-Step Workflow

### Step 1: Select Examples

```python
from survey_generation_toolkit import select_examples

matches = select_examples(
    category="premium skincare",
    audience="Women 25-54 who spend $50+/month on skincare",
    objective="pricing for new product launch",
    methodology="pricing",
    top_n=3
)
```

### Step 2: Build Prompt

```python
from survey_generation_toolkit import build_generation_prompt

prompt = build_generation_prompt(
    examples=matches,
    category="premium skincare",
    audience="Women 25-54 who spend $50+/month on skincare",
    objective="pricing for new product launch",
    methodology="pricing",
    planned_analyses=["crosstabs"],
    loi_target=10
)
```

### Step 3: Generate Questionnaire

### Step 4: Validate

```python
from survey_generation_toolkit import validate_survey

report = validate_survey(
    survey,
    planned_analyses=["crosstabs"],
    methodology="pricing"
)
```

This runs structural validators + `validate_pricing()`.

---

## Section Order (Standard Pricing Study)

| Order | Section | Typical # Questions | Purpose |
|---|---|---|---|
| 1 | Screener | 3-5 | Qualify category purchasers with price awareness |
| 2 | Category Context | 3-5 | Establish spending reference frame |
| 3 | Product/Concept Exposure | 1 | Show what is being priced (no price shown) |
| 4 | Pricing Exercise | 4-8 | Van Westendorp and/or Gabor-Granger |
| 5 | Purchase Intent at Price | 1-3 | Intent at specific price points |
| 6 | Value Perceptions | 3-5 | Perceived value, price-quality trade-offs |
| 7 | Demographics | 5-8 | Classification |

**LOI guidance:** 8-12 minutes. Pricing studies are typically short and focused.

---

## Van Westendorp Price Sensitivity Meter (PSM)

Four open-numeric questions in this exact order:

1. **Too Expensive:** "At what price would you consider this product to be so expensive that you would NOT consider buying it?"
2. **Too Cheap:** "At what price would you consider this product to be priced so low that you would question its quality?"
3. **Expensive (High Side):** "At what price would you consider this product is starting to get expensive, but you still might consider it?"
4. **Bargain (Good Value):** "At what price would you consider this product to be a bargain — a great buy for the money?"

### Logical Constraints

The four prices must satisfy: Too Cheap < Good Value < Expensive < Too Expensive

Include validation logic in programming_logic:
```
programming_logic: {
    validate: "too_cheap < bargain < expensive < too_expensive",
    on_fail: "prompt_respondent_to_correct"
}
```

### Analysis Output

Van Westendorp produces four key price points:
- **Point of Marginal Cheapness (PMC):** intersection of Too Cheap and Expensive curves
- **Point of Marginal Expensiveness (PME):** intersection of Too Expensive and Bargain curves
- **Indifference Price Point (IDP):** intersection of Expensive and Bargain curves
- **Optimal Price Point (OPP):** intersection of Too Cheap and Too Expensive curves

---

## Gabor-Granger Methodology

Sequential purchase intent at specific price points:

1. Start at a mid-range price
2. If respondent would buy → increase price, ask again
3. If respondent would not buy → decrease price, ask again
4. Continue for 5-7 price points total

### Design Requirements

- Define the price ladder (5-7 evenly spaced points)
- Use 5-point purchase intent scale at each price point
- Specify the starting price and step direction in programming_logic
- Example ladder for a $30-$60 range: $30, $35, $40, $45, $50, $55, $60

```
programming_logic: {
    price_ladder: [30, 35, 40, 45, 50, 55, 60],
    start_at: "midpoint",
    direction_if_buy: "up",
    direction_if_not_buy: "down"
}
```

---

## Category Context Section

Establish reference frame before pricing questions:
- Current spend in category (open numeric or ranges)
- Price last paid for a similar product
- Brands currently purchased and their perceived price tier
- Price sensitivity self-assessment

This section prevents "sticker shock" by anchoring respondents in the category's price reality.

---

## Common Pitfalls

| Pitfall | Why It Breaks | Fix |
|---|---|---|
| No product exposure before pricing | Respondents don't know what they're pricing | Always show product/concept first |
| Wrong VW question order | Distorts the cumulative frequency curves | Follow exact 4-question order |
| No logical validation on VW prices | Nonsensical price relationships | Add validation logic |
| GG price ladder too wide | Unrealistic prices bias results | Base ladder on category norms |
| No category context / anchoring | Respondents have no reference frame | Include current spend questions |
| Showing price in product exposure | Anchoring bias on subsequent pricing Qs | Never show price in exposure |
