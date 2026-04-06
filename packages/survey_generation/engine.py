"""Section-based questionnaire generation engine.

Takes a draft config + assistant context and produces a Questionnaire.
Generation is section-by-section, only for selected sections, in the
order defined by the methodology matrix.

The current implementation uses deterministic templates. The LLM
integration point is isolated in _generate_section_content() which
can be swapped to call an LLM without changing the engine contract.
"""

from __future__ import annotations

from typing import Any

from packages.shared.assistant_context import (
    AssistantContext,
    Methodology,
    WorkflowStage,
    validate_for_stage,
)
from packages.shared.assistant_shell import compute_context_hash
from packages.shared.draft_config import DraftConfig
from packages.shared.questionnaire_schema import (
    Question,
    QuestionType,
    Questionnaire,
    ResponseOption,
    Section,
)
from packages.shared.section_taxonomy import SectionType, get_matrix


class GenerationError(Exception):
    """Raised when questionnaire generation fails."""


# ---------------------------------------------------------------------------
# Section content generators — deterministic templates per section type
# ---------------------------------------------------------------------------

def _gen_screener(ctx: AssistantContext, order: int) -> Section:
    audience = ""
    category = ""
    if ctx.brief:
        audience = ctx.brief.audience or "target respondents"
        category = ctx.brief.category or "the category"

    questions = [
        Question(
            question_id="SCR_01",
            question_text=f"Which of the following best describes your experience with {category}?",
            question_type=QuestionType.SINGLE_SELECT,
            var_name="SCR_01",
            response_options=[
                ResponseOption(code=1, label="I currently use/purchase"),
                ResponseOption(code=2, label="I have used/purchased in the past"),
                ResponseOption(code=3, label="I am aware but have not used/purchased"),
                ResponseOption(code=4, label="I am not aware", terminates=True),
            ],
        ),
        Question(
            question_id="SCR_02",
            question_text=f"How frequently do you purchase or use products in {category}?",
            question_type=QuestionType.SINGLE_SELECT,
            var_name="SCR_02",
            response_options=[
                ResponseOption(code=1, label="Daily"),
                ResponseOption(code=2, label="Weekly"),
                ResponseOption(code=3, label="Monthly"),
                ResponseOption(code=4, label="A few times a year"),
                ResponseOption(code=5, label="Rarely or never", terminates=True),
            ],
        ),
        Question(
            question_id="SCR_03",
            question_text=f"Are you between the ages specified for {audience}?",
            question_type=QuestionType.SINGLE_SELECT,
            var_name="SCR_03",
            response_options=[
                ResponseOption(code=1, label="Yes"),
                ResponseOption(code=2, label="No", terminates=True),
            ],
        ),
    ]
    return Section(
        section_id="screener",
        section_type=SectionType.SCREENER.value,
        label="Screener",
        order=order,
        questions=questions,
    )


def _gen_demographics(ctx: AssistantContext, order: int) -> Section:
    questions = [
        Question(question_id="DEM_01", question_text="What is your age?", question_type=QuestionType.NUMERIC, var_name="DEM_01"),
        Question(
            question_id="DEM_02", question_text="What is your gender?", question_type=QuestionType.SINGLE_SELECT, var_name="DEM_02",
            response_options=[
                ResponseOption(code=1, label="Male"),
                ResponseOption(code=2, label="Female"),
                ResponseOption(code=3, label="Non-binary"),
                ResponseOption(code=4, label="Prefer not to say"),
            ],
        ),
        Question(
            question_id="DEM_03", question_text="What is your household income?", question_type=QuestionType.SINGLE_SELECT, var_name="DEM_03",
            response_options=[
                ResponseOption(code=1, label="Under $25,000"),
                ResponseOption(code=2, label="$25,000 - $49,999"),
                ResponseOption(code=3, label="$50,000 - $74,999"),
                ResponseOption(code=4, label="$75,000 - $99,999"),
                ResponseOption(code=5, label="$100,000 - $149,999"),
                ResponseOption(code=6, label="$150,000+"),
                ResponseOption(code=7, label="Prefer not to say"),
            ],
        ),
        Question(
            question_id="DEM_04", question_text="What region do you live in?", question_type=QuestionType.SINGLE_SELECT, var_name="DEM_04",
            response_options=[
                ResponseOption(code=1, label="Northeast"),
                ResponseOption(code=2, label="Midwest"),
                ResponseOption(code=3, label="South"),
                ResponseOption(code=4, label="West"),
            ],
        ),
    ]
    return Section(
        section_id="demographics",
        section_type=SectionType.DEMOGRAPHICS.value,
        label="Demographics",
        order=order,
        questions=questions,
    )


def _gen_attitudes(ctx: AssistantContext, order: int) -> Section:
    category = ctx.brief.category if ctx.brief and ctx.brief.category else "this category"
    items = [
        f"I carefully research products before purchasing in {category}",
        f"I am loyal to my preferred brands in {category}",
        f"Price is the most important factor when choosing in {category}",
        f"I enjoy trying new products in {category}",
        f"Quality matters more than brand name in {category}",
        f"I trust recommendations from friends and family for {category}",
        f"Sustainability influences my choices in {category}",
        f"I am satisfied with the options available in {category}",
        f"Convenience is a key factor in my {category} decisions",
        f"I am willing to pay more for premium products in {category}",
        f"I often purchase {category} products on impulse",
        f"Online reviews influence my {category} purchases",
        f"I feel emotionally connected to certain brands in {category}",
        f"Innovation is important to me in {category}",
        f"I consider health/wellness when choosing in {category}",
    ]
    questions = [
        Question(
            question_id=f"ATT_{i+1:02d}",
            question_text=stmt,
            question_type=QuestionType.LIKERT_SCALE,
            var_name=f"ATT_{i+1:02d}",
            scale_points=5,
            scale_labels={1: "Strongly Disagree", 2: "Disagree", 3: "Neutral", 4: "Agree", 5: "Strongly Agree"},
        )
        for i, stmt in enumerate(items)
    ]
    return Section(
        section_id="attitudes",
        section_type=SectionType.ATTITUDES.value,
        label="Attitudinal Battery",
        order=order,
        questions=questions,
        metadata={"scale_type": "5-point Likert", "var_prefix": "ATT"},
    )


def _gen_category_behavior(ctx: AssistantContext, order: int) -> Section:
    category = ctx.brief.category if ctx.brief and ctx.brief.category else "this category"
    questions = [
        Question(
            question_id="BEH_01",
            question_text=f"How often do you purchase products in {category}?",
            question_type=QuestionType.SINGLE_SELECT,
            var_name="BEH_01",
            response_options=[
                ResponseOption(code=1, label="Daily"),
                ResponseOption(code=2, label="Several times a week"),
                ResponseOption(code=3, label="Weekly"),
                ResponseOption(code=4, label="Monthly"),
                ResponseOption(code=5, label="A few times a year"),
            ],
        ),
        Question(
            question_id="BEH_02",
            question_text=f"Where do you typically purchase {category} products?",
            question_type=QuestionType.MULTI_SELECT,
            var_name="BEH_02",
            response_options=[
                ResponseOption(code=1, label="Grocery store"),
                ResponseOption(code=2, label="Online retailer"),
                ResponseOption(code=3, label="Specialty store"),
                ResponseOption(code=4, label="Convenience store"),
                ResponseOption(code=5, label="Club/warehouse store"),
            ],
        ),
        Question(
            question_id="BEH_03",
            question_text=f"How much do you typically spend per month on {category}?",
            question_type=QuestionType.SINGLE_SELECT,
            var_name="BEH_03",
            response_options=[
                ResponseOption(code=1, label="Under $10"),
                ResponseOption(code=2, label="$10 - $24"),
                ResponseOption(code=3, label="$25 - $49"),
                ResponseOption(code=4, label="$50 - $99"),
                ResponseOption(code=5, label="$100+"),
            ],
        ),
    ]
    return Section(
        section_id="category_behavior",
        section_type=SectionType.CATEGORY_BEHAVIOR.value,
        label="Category Behavior",
        order=order,
        questions=questions,
    )


def _gen_satisfaction_outcomes(ctx: AssistantContext, order: int) -> Section:
    category = ctx.brief.category if ctx.brief and ctx.brief.category else "this category"
    questions = [
        Question(
            question_id="SAT_01",
            question_text=f"Overall, how satisfied are you with the products you use in {category}?",
            question_type=QuestionType.LIKERT_SCALE,
            var_name="SAT_01",
            scale_points=5,
            scale_labels={1: "Very Dissatisfied", 2: "Dissatisfied", 3: "Neutral", 4: "Satisfied", 5: "Very Satisfied"},
        ),
        Question(
            question_id="SAT_02",
            question_text=f"How likely are you to recommend your preferred {category} brand to others?",
            question_type=QuestionType.NUMERIC,
            var_name="SAT_02",
            scale_points=11,
            scale_labels={0: "Not at all likely", 10: "Extremely likely"},
        ),
    ]
    return Section(
        section_id="satisfaction_outcomes",
        section_type=SectionType.SATISFACTION_OUTCOMES.value,
        label="Satisfaction & Outcomes",
        order=order,
        questions=questions,
        metadata={"dv_flag": True},
    )


def _gen_brand_awareness(ctx: AssistantContext, order: int) -> Section:
    questions = [
        Question(
            question_id="BA_01",
            question_text="When you think of this category, what brands come to mind? (Unaided)",
            question_type=QuestionType.OPEN_ENDED,
            var_name="BA_01",
        ),
        Question(
            question_id="BA_02",
            question_text="Which of the following brands have you heard of? (Aided)",
            question_type=QuestionType.MULTI_SELECT,
            var_name="BA_02",
            response_options=[
                ResponseOption(code=1, label="[Brand A]"),
                ResponseOption(code=2, label="[Brand B]"),
                ResponseOption(code=3, label="[Brand C]"),
                ResponseOption(code=4, label="[Brand D]"),
                ResponseOption(code=5, label="None of these"),
            ],
        ),
    ]
    return Section(
        section_id="brand_awareness",
        section_type=SectionType.BRAND_AWARENESS.value,
        label="Brand Awareness",
        order=order,
        questions=questions,
        metadata={"awareness_type": "unaided_then_aided"},
    )


def _gen_brand_perceptions(ctx: AssistantContext, order: int) -> Section:
    questions = [
        Question(
            question_id="BP_01",
            question_text="How would you rate each brand on the following attributes?",
            question_type=QuestionType.LIKERT_SCALE,
            var_name="BP_01",
            scale_points=5,
            scale_labels={1: "Poor", 5: "Excellent"},
        ),
    ]
    return Section(
        section_id="brand_perceptions",
        section_type=SectionType.BRAND_PERCEPTIONS.value,
        label="Brand Perceptions",
        order=order,
        questions=questions,
    )


def _gen_maxdiff_exercise(ctx: AssistantContext, order: int) -> Section:
    questions = [
        Question(
            question_id=f"MD_{i+1:02d}",
            question_text=f"MaxDiff Task {i+1}: Select BEST and WORST",
            question_type=QuestionType.MAXDIFF_TASK,
            var_name=f"MD_{i+1:02d}",
        )
        for i in range(12)
    ]
    return Section(
        section_id="maxdiff_exercise",
        section_type=SectionType.MAXDIFF_EXERCISE.value,
        label="MaxDiff Exercise",
        order=order,
        questions=questions,
        metadata={"items_per_task": 4, "num_tasks": 12},
    )


def _gen_placeholder(section_type: str, label: str, ctx: AssistantContext, order: int) -> Section:
    """Generate a placeholder section for types without a dedicated generator."""
    # Use section_type hash to guarantee unique IDs across similar-prefix sections
    import hashlib
    prefix = hashlib.md5(section_type.encode()).hexdigest()[:4].upper()
    return Section(
        section_id=section_type,
        section_type=section_type,
        label=label,
        order=order,
        questions=[
            Question(
                question_id=f"{prefix}_01",
                question_text=f"[Placeholder for {label}]",
                question_type=QuestionType.OPEN_ENDED,
                var_name=f"{prefix}_01",
            ),
        ],
        metadata={"placeholder": True},
    )


# Section type -> generator function
_GENERATORS: dict[str, Any] = {
    SectionType.SCREENER.value: _gen_screener,
    SectionType.DEMOGRAPHICS.value: _gen_demographics,
    SectionType.ATTITUDES.value: _gen_attitudes,
    SectionType.CATEGORY_BEHAVIOR.value: _gen_category_behavior,
    SectionType.SATISFACTION_OUTCOMES.value: _gen_satisfaction_outcomes,
    SectionType.BRAND_AWARENESS.value: _gen_brand_awareness,
    SectionType.BRAND_PERCEPTIONS.value: _gen_brand_perceptions,
    SectionType.MAXDIFF_EXERCISE.value: _gen_maxdiff_exercise,
}


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

def generate_questionnaire(
    draft: DraftConfig,
    ctx: AssistantContext,
) -> Questionnaire:
    """Generate a questionnaire from a draft config and assistant context.

    AC-1: Generation payload includes assistant context contract.
    AC-2: Only selected sections are generated.
    AC-3: Output conforms to schema and section order.
    """
    # AC-1: Validate context contract
    validate_for_stage(ctx)

    matrix = get_matrix(draft.methodology)
    context_hash = compute_context_hash(ctx)

    # AC-2 + AC-3: Generate only selected sections, in matrix order
    sections: list[Section] = []
    order = 0
    for section_type in matrix.section_order:
        st_value = section_type.value
        if st_value in draft.selected_sections or matrix.sections[section_type].required:
            generator = _GENERATORS.get(st_value)
            if generator:
                section = generator(ctx, order)
            else:
                defn = matrix.sections[section_type]
                section = _gen_placeholder(st_value, defn.label, ctx, order)
            sections.append(section)
            order += 1

    # Estimate LOI
    total_q = sum(len(s.questions) for s in sections)
    estimated_loi = max(1, total_q // 3)  # rough: ~3 questions per minute

    return Questionnaire(
        project_id=draft.project_id,
        methodology=draft.methodology.value,
        sections=sections,
        estimated_loi_minutes=estimated_loi,
        draft_id=draft.draft_id,
        brief_id=ctx.brief.brief_id if ctx.brief else None,
        context_hash=context_hash,
    )
