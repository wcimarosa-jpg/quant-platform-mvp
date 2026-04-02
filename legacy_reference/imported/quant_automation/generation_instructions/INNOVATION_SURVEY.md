# Innovation / Feature Exploration Survey Generation — Agent Instructions

## Purpose

Generate a complete, analysis-ready innovation and feature exploration questionnaire. Innovation studies identify unmet needs, prioritize potential features, and evaluate innovation concepts. They often combine MaxDiff for feature prioritization with attitudinal batteries for need-state clustering. The generated survey must be compatible with the analysis pipeline defined in `ANALYTIC_COMPATIBILITY.md`.

---

## Prerequisites

### Required Inputs

| Input | Source | Description |
|-------|--------|-------------|
| Category / industry | User-provided | e.g., "smart home devices", "digital banking" |
| Target audience | User-provided | e.g., "Homeowners 30-55 with interest in home automation" |
| Study objective | User-provided | e.g., "Prioritize 25 potential features for next product generation" |
| Innovation scope | User-provided | feature_prioritization, whitespace_exploration, or concept_optimization |
| Feature list | User-provided (if available) | Features/innovations to evaluate |
| Planned analyses | User-provided or inferred | maxdiff, kmeans, crosstabs |
| LOI target | User-provided (optional) | Survey length in minutes (default: 15-20 min) |

---

## Step-by-Step Workflow

### Step 1: Select Examples

```python
from survey_generation_toolkit import select_examples

matches = select_examples(
    category="smart home devices",
    audience="Homeowners 30-55 interested in home automation",
    objective="feature prioritization for product development",
    methodology="innovation",
    top_n=3
)
```

### Step 2: Build Prompt

```python
from survey_generation_toolkit import build_generation_prompt

prompt = build_generation_prompt(
    examples=matches,
    category="smart home devices",
    audience="Homeowners 30-55 interested in home automation",
    objective="feature prioritization for product development",
    methodology="innovation",
    planned_analyses=["maxdiff", "crosstabs", "kmeans"],
    loi_target=18
)
```

### Step 3: Generate Questionnaire

### Step 4: Validate

```python
from survey_generation_toolkit import validate_survey

report = validate_survey(
    survey,
    planned_analyses=["maxdiff", "crosstabs", "kmeans"],
    methodology="innovation"
)
```

This runs structural validators + analysis validators + `validate_innovation()`.

---

## Section Order (Standard Innovation Study)

| Order | Section | Typical # Questions | Purpose |
|---|---|---|---|
| 1 | Screener | 3-5 | Qualify current category users |
| 2 | Current State & Pain Points | 5-8 | Establish problem space, unmet needs |
| 3 | Feature Descriptions | Variable | Brief feature/innovation descriptions |
| 4 | Feature MaxDiff | 12-15 tasks | Best-worst scaling for prioritization |
| 5 | Feature Diagnostics | 3-5 per feature subset | Deeper evaluation of top features |
| 6 | Innovation Attitudes | 10-15 statements | Attitudes for need-state clustering |
| 7 | Overall Concept Appeal | 2-3 | Interest, purchase intent, switch intent |
| 8 | Demographics | 5-8 | Classification |

**LOI guidance:** 15-20 minutes. MaxDiff + attitudes consume ~60% of LOI.

---

## Current State & Pain Points Section

Establish the problem space before introducing features:

- **Current usage:** What products/solutions respondents currently use
- **Satisfaction:** Satisfaction with current options (5-point scale)
- **Unmet needs:** Open-end or aided multi-select of pain points
- **Workarounds:** What respondents do to compensate for missing features
- **Whitespace prompt:** "What would make [category] significantly better?" (open-end)

This section serves dual purposes:
1. Contextualizes feature evaluation (respondents think about real needs)
2. Provides unmet-need data for whitespace analysis

---

## Feature Description & MaxDiff Design

### Feature Descriptions
- 1-2 sentences per feature, consistent format
- Clear benefit statement, not technical specifications
- Group into logical categories (convenience, quality, technology, etc.)
- These feed directly into the MaxDiff item list

### Feature MaxDiff
- 15-30 feature items
- 4 items per set, 12-15 sets
- Evaluation dimension: "most important" / "least important"
- BIB design with equal item exposure
- If bundling planned: ensure items span logical groupings

### Feature Bundling (post-design)
Bundles are analytical constructs defined after the MaxDiff design:
- Group features that could form product configurations
- 3-5 items per bundle
- Bundles can overlap (same feature in multiple bundles)
- Bundle analysis uses MaxDiff utilities, not separate survey questions

---

## Innovation Attitudes Section

10-15 statements on a uniform 5-point agreement scale:

| Theme | Example Statements |
|---|---|
| Technology adoption | "I'm usually among the first to try new technology" |
| Change openness | "I'm comfortable switching to a new product if it's better" |
| Price sensitivity | "I'd pay significantly more for cutting-edge features" |
| Category expertise | "I consider myself very knowledgeable about [category]" |
| Risk tolerance | "I don't mind being an early adopter even if there are bugs" |

If K-Means clustering is planned, this battery must follow clustering rules:
- Minimum 15 items for meaningful segmentation
- Single uniform scale throughout
- Span multiple conceptual dimensions

---

## Innovation Scope Guidelines

### Feature Prioritization
- Focus: rank a defined feature set by importance
- MaxDiff is the centerpiece
- Feature diagnostics for top-ranked items
- Output: feature priority ranking with utilities

### Whitespace Exploration
- Focus: identify unmet needs and opportunity areas
- Heavier current-state section with open-ends
- Lighter MaxDiff (if features are hypothetical)
- Attitudinal battery for need-state clustering
- Output: need clusters + feature-by-cluster preferences

### Concept Optimization
- Focus: configure optimal product from feature components
- MaxDiff + bundle analysis
- Feature diagnostics for all items (not just top)
- Purchase intent for configured bundles
- Output: optimal bundle configuration with demand estimate

---

## Common Pitfalls

| Pitfall | Why It Breaks | Fix |
|---|---|---|
| No current-state context | Features evaluated in a vacuum | Establish problem space first |
| Technical feature descriptions | Respondents can't evaluate what they don't understand | Use benefit language |
| Overlapping features in MaxDiff | Suppresses both items' utilities | Ensure distinct concepts |
| No attitudinal battery when clustering planned | K-Means has no input | Include 15+ attitude statements |
| Feature diagnostics for ALL items | LOI blowout | Evaluate only top-ranked subset |
| Missing overall concept appeal | No demand signal | Include purchase intent DV |
