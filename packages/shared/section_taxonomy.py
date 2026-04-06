"""Section taxonomy and generation matrix v1.

Defines the canonical section types available per methodology,
their required fields, validation rules, and ordering.
Consumable by UI selectors and the generation engine.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .assistant_context import Methodology

TAXONOMY_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Section identifiers — the universe of section types
# ---------------------------------------------------------------------------

class SectionType(str, Enum):
    SCREENER = "screener"
    CATEGORY_BEHAVIOR = "category_behavior"
    BRAND_AWARENESS = "brand_awareness"
    BRAND_PERCEPTIONS = "brand_perceptions"
    ATTITUDES = "attitudes"
    MOTIVATIONS = "motivations"
    PURCHASE_FUNNEL = "purchase_funnel"
    ENGAGEMENT_JOURNEY = "engagement_journey"
    OCCASION_USAGE = "occasion_usage"
    IDENTITY_VALUES = "identity_values"
    SATISFACTION_OUTCOMES = "satisfaction_outcomes"
    CONCEPT_EXPOSURE = "concept_exposure"
    CONCEPT_DIAGNOSTICS = "concept_diagnostics"
    MESSAGE_EXPOSURE = "message_exposure"
    MESSAGE_DIAGNOSTICS = "message_diagnostics"
    MAXDIFF_EXERCISE = "maxdiff_exercise"
    MAXDIFF_FOLLOWUP = "maxdiff_followup"
    PRICING_EXERCISE = "pricing_exercise"
    INNOVATION_NEEDS = "innovation_needs"
    INNOVATION_FEATURES = "innovation_features"
    DEMOGRAPHICS = "demographics"


# ---------------------------------------------------------------------------
# Section definition — what the UI and generation engine consume
# ---------------------------------------------------------------------------

class SectionDefinition(BaseModel):
    """A single section in the taxonomy."""

    section_type: SectionType
    label: str
    description: str
    typical_question_count: tuple[int, int]  # (min, max)
    required: bool = False
    required_fields: list[str] = Field(default_factory=list)
    validation_rules: list[str] = Field(default_factory=list)
    analysis_dependencies: list[str] = Field(default_factory=list)


class MethodologyMatrix(BaseModel):
    """Full section matrix for one methodology."""

    methodology: Methodology
    label: str
    description: str
    default_loi_minutes: tuple[int, int]  # (min, max)
    section_order: list[SectionType]
    sections: dict[SectionType, SectionDefinition]

    def required_sections(self) -> list[SectionType]:
        return [st for st in self.section_order if self.sections[st].required]

    def optional_sections(self) -> list[SectionType]:
        return [st for st in self.section_order if not self.sections[st].required]

    def for_ui(self) -> list[dict[str, Any]]:
        """Return a list of dicts suitable for a UI selector component."""
        return [
            {
                "section_type": st.value,
                "label": self.sections[st].label,
                "description": self.sections[st].description,
                "required": self.sections[st].required,
                "typical_questions": list(self.sections[st].typical_question_count),
            }
            for st in self.section_order
        ]

    def for_generation(self, selected: list[str]) -> list[dict[str, Any]]:
        """Return section specs for the generation engine, filtered to selected sections."""
        out: list[dict[str, Any]] = []
        for st in self.section_order:
            if st.value in selected or self.sections[st].required:
                defn = self.sections[st]
                out.append({
                    "section_type": st.value,
                    "label": defn.label,
                    "typical_question_count": list(defn.typical_question_count),
                    "required_fields": defn.required_fields,
                    "validation_rules": defn.validation_rules,
                    "analysis_dependencies": defn.analysis_dependencies,
                })
        return out


# ---------------------------------------------------------------------------
# Shared section builders — reusable across methodologies
# ---------------------------------------------------------------------------

def _screener(required: bool = True) -> SectionDefinition:
    return SectionDefinition(
        section_type=SectionType.SCREENER,
        label="Screener",
        description="Qualify respondents on category usage, brand awareness, or target criteria.",
        typical_question_count=(3, 6),
        required=required,
        required_fields=["question_id", "question_text", "response_options", "termination_rules"],
        validation_rules=["at_least_one_termination_rule", "exhaustive_response_codes"],
    )


def _demographics(required: bool = True) -> SectionDefinition:
    return SectionDefinition(
        section_type=SectionType.DEMOGRAPHICS,
        label="Demographics",
        description="Standard demographic profiling: age, gender, income, region, etc.",
        typical_question_count=(4, 8),
        required=required,
        required_fields=["question_id", "question_text", "response_options", "value_labels"],
        validation_rules=["exhaustive_response_codes", "mutually_exclusive_options"],
        analysis_dependencies=["crosstabs"],
    )


def _brand_awareness() -> SectionDefinition:
    return SectionDefinition(
        section_type=SectionType.BRAND_AWARENESS,
        label="Brand Awareness",
        description="Unaided and aided brand awareness with proper sequencing.",
        typical_question_count=(2, 4),
        required_fields=["question_id", "question_text", "response_options", "awareness_type"],
        validation_rules=["unaided_before_aided", "brand_list_matches_project"],
        analysis_dependencies=["crosstabs"],
    )


def _brand_perceptions() -> SectionDefinition:
    return SectionDefinition(
        section_type=SectionType.BRAND_PERCEPTIONS,
        label="Brand Perceptions",
        description="Rate brands on imagery/attribute grid. Uniform scale required.",
        typical_question_count=(1, 3),
        required_fields=["question_id", "question_text", "scale_points", "brand_list", "attribute_list"],
        validation_rules=["uniform_scale", "brand_list_matches_project"],
        analysis_dependencies=["crosstabs", "ridge_regression"],
    )


def _attitudes(min_q: int = 15, max_q: int = 40) -> SectionDefinition:
    return SectionDefinition(
        section_type=SectionType.ATTITUDES,
        label="Attitudinal Battery",
        description="Likert-scale statements covering attitudes, motivations, and beliefs. Uniform scale required for clustering.",
        typical_question_count=(min_q, max_q),
        required_fields=["question_id", "question_text", "scale_points", "scale_labels", "var_prefix"],
        validation_rules=["uniform_likert_scale", "min_15_items_for_clustering", "multi_dimensional_coverage"],
        analysis_dependencies=["kmeans", "varclus", "ridge_regression"],
    )


def _category_behavior() -> SectionDefinition:
    return SectionDefinition(
        section_type=SectionType.CATEGORY_BEHAVIOR,
        label="Category Behavior",
        description="Usage frequency, purchase channels, spending, and category engagement.",
        typical_question_count=(5, 12),
        required_fields=["question_id", "question_text", "response_options", "value_labels"],
        validation_rules=["exhaustive_response_codes"],
        analysis_dependencies=["crosstabs"],
    )


def _satisfaction_outcomes() -> SectionDefinition:
    return SectionDefinition(
        section_type=SectionType.SATISFACTION_OUTCOMES,
        label="Satisfaction & Outcomes",
        description="Overall satisfaction, NPS, purchase intent, or other dependent variables.",
        typical_question_count=(2, 5),
        required_fields=["question_id", "question_text", "scale_points", "scale_labels"],
        validation_rules=["numeric_scale", "dv_flag_set"],
        analysis_dependencies=["ridge_regression", "crosstabs"],
    )


# ---------------------------------------------------------------------------
# Per-methodology matrix definitions
# ---------------------------------------------------------------------------

def _build_segmentation() -> MethodologyMatrix:
    return MethodologyMatrix(
        methodology=Methodology.SEGMENTATION,
        label="Segmentation",
        description="Identify actionable consumer segments via attitudinal clustering and behavioral profiling.",
        default_loi_minutes=(15, 20),
        section_order=[
            SectionType.SCREENER,
            SectionType.CATEGORY_BEHAVIOR,
            SectionType.PURCHASE_FUNNEL,
            SectionType.OCCASION_USAGE,
            SectionType.ATTITUDES,
            SectionType.BRAND_PERCEPTIONS,
            SectionType.SATISFACTION_OUTCOMES,
            SectionType.DEMOGRAPHICS,
        ],
        sections={
            SectionType.SCREENER: _screener(),
            SectionType.CATEGORY_BEHAVIOR: SectionDefinition(
                section_type=SectionType.CATEGORY_BEHAVIOR,
                label="Behavioral Battery",
                description="Usage occasions, frequency, purchase channels. 15-20 items.",
                typical_question_count=(10, 20),
                required_fields=["question_id", "question_text", "response_options", "var_prefix"],
                validation_rules=["exhaustive_response_codes"],
                analysis_dependencies=["crosstabs", "varclus"],
            ),
            SectionType.PURCHASE_FUNNEL: SectionDefinition(
                section_type=SectionType.PURCHASE_FUNNEL,
                label="Purchase Funnel",
                description="Awareness, consideration, trial, repeat, loyalty stages.",
                typical_question_count=(4, 8),
                required_fields=["question_id", "question_text", "response_options"],
                validation_rules=["exhaustive_response_codes", "funnel_stage_ordering"],
                analysis_dependencies=["crosstabs"],
            ),
            SectionType.OCCASION_USAGE: SectionDefinition(
                section_type=SectionType.OCCASION_USAGE,
                label="Occasion / Usage Context",
                description="When, where, and why product is used. Context-driven segmentation input.",
                typical_question_count=(3, 8),
                required_fields=["question_id", "question_text", "response_options"],
                validation_rules=["exhaustive_response_codes"],
                analysis_dependencies=["crosstabs"],
            ),
            SectionType.ATTITUDES: _attitudes(20, 40),
            SectionType.BRAND_PERCEPTIONS: _brand_perceptions(),
            SectionType.SATISFACTION_OUTCOMES: _satisfaction_outcomes(),
            SectionType.DEMOGRAPHICS: _demographics(),
        },
    )


def _build_attitude_usage() -> MethodologyMatrix:
    return MethodologyMatrix(
        methodology=Methodology.ATTITUDE_USAGE,
        label="Attitude & Usage (A&U)",
        description="Measure brand health, category dynamics, and consumer behavior patterns.",
        default_loi_minutes=(15, 20),
        section_order=[
            SectionType.SCREENER,
            SectionType.BRAND_AWARENESS,
            SectionType.CATEGORY_BEHAVIOR,
            SectionType.BRAND_PERCEPTIONS,
            SectionType.ATTITUDES,
            SectionType.SATISFACTION_OUTCOMES,
            SectionType.DEMOGRAPHICS,
        ],
        sections={
            SectionType.SCREENER: _screener(),
            SectionType.BRAND_AWARENESS: _brand_awareness(),
            SectionType.CATEGORY_BEHAVIOR: _category_behavior(),
            SectionType.BRAND_PERCEPTIONS: _brand_perceptions(),
            SectionType.ATTITUDES: _attitudes(15, 30),
            SectionType.SATISFACTION_OUTCOMES: _satisfaction_outcomes(),
            SectionType.DEMOGRAPHICS: _demographics(),
        },
    )


def _build_drivers() -> MethodologyMatrix:
    return MethodologyMatrix(
        methodology=Methodology.DRIVERS,
        label="Drivers Analysis",
        description="Identify which attitudes and perceptions drive key outcomes via regression.",
        default_loi_minutes=(12, 18),
        section_order=[
            SectionType.SCREENER,
            SectionType.CATEGORY_BEHAVIOR,
            SectionType.ATTITUDES,
            SectionType.BRAND_PERCEPTIONS,
            SectionType.SATISFACTION_OUTCOMES,
            SectionType.DEMOGRAPHICS,
        ],
        sections={
            SectionType.SCREENER: _screener(),
            SectionType.CATEGORY_BEHAVIOR: _category_behavior(),
            SectionType.ATTITUDES: _attitudes(15, 35),
            SectionType.BRAND_PERCEPTIONS: _brand_perceptions(),
            SectionType.SATISFACTION_OUTCOMES: SectionDefinition(
                section_type=SectionType.SATISFACTION_OUTCOMES,
                label="Outcome / Dependent Variables",
                description="The outcomes to be explained: satisfaction, NPS, purchase intent. Critical for regression.",
                typical_question_count=(3, 6),
                required=True,
                required_fields=["question_id", "question_text", "scale_points", "scale_labels", "dv_flag"],
                validation_rules=["numeric_scale", "dv_flag_set", "min_2_dv_items"],
                analysis_dependencies=["ridge_regression", "crosstabs"],
            ),
            SectionType.DEMOGRAPHICS: _demographics(),
        },
    )


def _build_concept_monadic() -> MethodologyMatrix:
    return MethodologyMatrix(
        methodology=Methodology.CONCEPT_MONADIC,
        label="Concept Test (Monadic)",
        description="Evaluate new product/service concepts with exposure, diagnostics, and purchase intent.",
        default_loi_minutes=(10, 15),
        section_order=[
            SectionType.SCREENER,
            SectionType.CATEGORY_BEHAVIOR,
            SectionType.CONCEPT_EXPOSURE,
            SectionType.CONCEPT_DIAGNOSTICS,
            SectionType.SATISFACTION_OUTCOMES,
            SectionType.DEMOGRAPHICS,
        ],
        sections={
            SectionType.SCREENER: _screener(),
            SectionType.CATEGORY_BEHAVIOR: _category_behavior(),
            SectionType.CONCEPT_EXPOSURE: SectionDefinition(
                section_type=SectionType.CONCEPT_EXPOSURE,
                label="Concept Exposure",
                description="Present concept stimulus and capture initial reaction.",
                typical_question_count=(1, 3),
                required=True,
                required_fields=["question_id", "question_text", "stimulus_type", "exposure_design"],
                validation_rules=["stimulus_present", "exposure_design_valid"],
                analysis_dependencies=["crosstabs"],
            ),
            SectionType.CONCEPT_DIAGNOSTICS: SectionDefinition(
                section_type=SectionType.CONCEPT_DIAGNOSTICS,
                label="Concept Diagnostics",
                description="Detailed evaluation: appeal, uniqueness, believability, relevance, purchase intent.",
                typical_question_count=(5, 12),
                required=True,
                required_fields=["question_id", "question_text", "scale_points", "diagnostic_dimension"],
                validation_rules=["uniform_scale", "covers_core_diagnostics"],
                analysis_dependencies=["crosstabs", "ridge_regression"],
            ),
            SectionType.SATISFACTION_OUTCOMES: _satisfaction_outcomes(),
            SectionType.DEMOGRAPHICS: _demographics(),
        },
    )


def _build_creative_monadic() -> MethodologyMatrix:
    return MethodologyMatrix(
        methodology=Methodology.CREATIVE_MONADIC,
        label="Creative Test (Monadic)",
        description="Evaluate advertising or creative executions with exposure and diagnostic batteries.",
        default_loi_minutes=(10, 15),
        section_order=[
            SectionType.SCREENER,
            SectionType.CATEGORY_BEHAVIOR,
            SectionType.MESSAGE_EXPOSURE,
            SectionType.MESSAGE_DIAGNOSTICS,
            SectionType.SATISFACTION_OUTCOMES,
            SectionType.DEMOGRAPHICS,
        ],
        sections={
            SectionType.SCREENER: _screener(),
            SectionType.CATEGORY_BEHAVIOR: _category_behavior(),
            SectionType.MESSAGE_EXPOSURE: SectionDefinition(
                section_type=SectionType.MESSAGE_EXPOSURE,
                label="Creative Exposure",
                description="Present creative stimulus (ad, video, copy) and capture initial reaction.",
                typical_question_count=(1, 3),
                required=True,
                required_fields=["question_id", "question_text", "stimulus_type", "exposure_design"],
                validation_rules=["stimulus_present", "exposure_design_valid"],
                analysis_dependencies=["crosstabs"],
            ),
            SectionType.MESSAGE_DIAGNOSTICS: SectionDefinition(
                section_type=SectionType.MESSAGE_DIAGNOSTICS,
                label="Creative Diagnostics",
                description="Comprehension, believability, relevance, motivation, brand fit.",
                typical_question_count=(5, 12),
                required=True,
                required_fields=["question_id", "question_text", "scale_points", "diagnostic_dimension"],
                validation_rules=["uniform_scale", "covers_core_diagnostics"],
                analysis_dependencies=["crosstabs", "ridge_regression"],
            ),
            SectionType.SATISFACTION_OUTCOMES: _satisfaction_outcomes(),
            SectionType.DEMOGRAPHICS: _demographics(),
        },
    )


def _build_brand_equity_tracker() -> MethodologyMatrix:
    return MethodologyMatrix(
        methodology=Methodology.BRAND_EQUITY_TRACKER,
        label="Brand Equity Tracker",
        description="Track brand health over time with awareness funnels, perceptions, and equity metrics.",
        default_loi_minutes=(12, 18),
        section_order=[
            SectionType.SCREENER,
            SectionType.BRAND_AWARENESS,
            SectionType.CATEGORY_BEHAVIOR,
            SectionType.BRAND_PERCEPTIONS,
            SectionType.ATTITUDES,
            SectionType.SATISFACTION_OUTCOMES,
            SectionType.DEMOGRAPHICS,
        ],
        sections={
            SectionType.SCREENER: _screener(),
            SectionType.BRAND_AWARENESS: SectionDefinition(
                section_type=SectionType.BRAND_AWARENESS,
                label="Brand Awareness Funnel",
                description="Unaided recall, aided awareness, consideration, trial. Must sequence unaided before aided.",
                typical_question_count=(3, 6),
                required=True,
                required_fields=["question_id", "question_text", "response_options", "awareness_type", "brand_list"],
                validation_rules=["unaided_before_aided", "brand_list_matches_project", "funnel_stage_ordering"],
                analysis_dependencies=["crosstabs"],
            ),
            SectionType.CATEGORY_BEHAVIOR: _category_behavior(),
            SectionType.BRAND_PERCEPTIONS: _brand_perceptions(),
            SectionType.ATTITUDES: _attitudes(10, 25),
            SectionType.SATISFACTION_OUTCOMES: _satisfaction_outcomes(),
            SectionType.DEMOGRAPHICS: _demographics(),
        },
    )


def _build_maxdiff() -> MethodologyMatrix:
    return MethodologyMatrix(
        methodology=Methodology.MAXDIFF,
        label="MaxDiff (Best-Worst Scaling)",
        description="Prioritize items via best-worst scaling with HB estimation.",
        default_loi_minutes=(12, 18),
        section_order=[
            SectionType.SCREENER,
            SectionType.CATEGORY_BEHAVIOR,
            SectionType.MAXDIFF_EXERCISE,
            SectionType.MAXDIFF_FOLLOWUP,
            SectionType.DEMOGRAPHICS,
        ],
        sections={
            SectionType.SCREENER: _screener(),
            SectionType.CATEGORY_BEHAVIOR: SectionDefinition(
                section_type=SectionType.CATEGORY_BEHAVIOR,
                label="Context & Warm-up",
                description="Orient respondent and establish evaluation frame before MaxDiff tasks.",
                typical_question_count=(3, 5),
                required_fields=["question_id", "question_text", "response_options"],
                validation_rules=["exhaustive_response_codes"],
                analysis_dependencies=["crosstabs"],
            ),
            SectionType.MAXDIFF_EXERCISE: SectionDefinition(
                section_type=SectionType.MAXDIFF_EXERCISE,
                label="MaxDiff Exercise",
                description="Core best-worst scaling tasks. Items must be comparable within a single evaluative dimension.",
                typical_question_count=(12, 15),
                required=True,
                required_fields=["question_id", "item_list", "items_per_task", "num_tasks", "dimension_label"],
                validation_rules=["bib_design_valid", "items_single_dimension", "min_12_tasks"],
                analysis_dependencies=["maxdiff", "maxdiff_regression"],
            ),
            SectionType.MAXDIFF_FOLLOWUP: SectionDefinition(
                section_type=SectionType.MAXDIFF_FOLLOWUP,
                label="MaxDiff Follow-up",
                description="Stated preference rating matching MaxDiff items for validation.",
                typical_question_count=(1, 2),
                required_fields=["question_id", "question_text", "scale_points", "item_list"],
                validation_rules=["items_match_maxdiff_exercise"],
                analysis_dependencies=["maxdiff"],
            ),
            SectionType.DEMOGRAPHICS: _demographics(),
        },
    )


def _build_turf() -> MethodologyMatrix:
    return MethodologyMatrix(
        methodology=Methodology.TURF,
        label="TURF (Total Unduplicated Reach & Frequency)",
        description="Optimize product/feature portfolios for maximum reach.",
        default_loi_minutes=(12, 18),
        section_order=[
            SectionType.SCREENER,
            SectionType.CATEGORY_BEHAVIOR,
            SectionType.MAXDIFF_EXERCISE,
            SectionType.INNOVATION_NEEDS,
            SectionType.INNOVATION_FEATURES,
            SectionType.DEMOGRAPHICS,
        ],
        sections={
            SectionType.SCREENER: _screener(),
            SectionType.CATEGORY_BEHAVIOR: _category_behavior(),
            SectionType.MAXDIFF_EXERCISE: SectionDefinition(
                section_type=SectionType.MAXDIFF_EXERCISE,
                label="Feature Prioritization (MaxDiff)",
                description="Best-worst scaling to rank features/items for TURF input.",
                typical_question_count=(12, 15),
                required=True,
                required_fields=["question_id", "item_list", "items_per_task", "num_tasks", "dimension_label"],
                validation_rules=["bib_design_valid", "items_single_dimension", "min_12_tasks"],
                analysis_dependencies=["maxdiff", "turf"],
            ),
            SectionType.INNOVATION_NEEDS: SectionDefinition(
                section_type=SectionType.INNOVATION_NEEDS,
                label="Current Pain Points & Needs",
                description="Identify unmet needs and current product gaps.",
                typical_question_count=(3, 8),
                required_fields=["question_id", "question_text", "response_options"],
                validation_rules=["exhaustive_response_codes"],
                analysis_dependencies=["crosstabs"],
            ),
            SectionType.INNOVATION_FEATURES: SectionDefinition(
                section_type=SectionType.INNOVATION_FEATURES,
                label="Feature Acceptance",
                description="Binary acceptance data per feature for TURF reach calculation.",
                typical_question_count=(1, 3),
                required=True,
                required_fields=["question_id", "question_text", "item_list", "acceptance_threshold"],
                validation_rules=["binary_acceptance_coding", "items_match_maxdiff_exercise"],
                analysis_dependencies=["turf"],
            ),
            SectionType.DEMOGRAPHICS: _demographics(),
        },
    )


# ---------------------------------------------------------------------------
# Registry — the single lookup point
# ---------------------------------------------------------------------------

METHODOLOGY_MATRIX: dict[Methodology, MethodologyMatrix] = {
    Methodology.SEGMENTATION: _build_segmentation(),
    Methodology.ATTITUDE_USAGE: _build_attitude_usage(),
    Methodology.DRIVERS: _build_drivers(),
    Methodology.CONCEPT_MONADIC: _build_concept_monadic(),
    Methodology.CREATIVE_MONADIC: _build_creative_monadic(),
    Methodology.BRAND_EQUITY_TRACKER: _build_brand_equity_tracker(),
    Methodology.MAXDIFF: _build_maxdiff(),
    Methodology.TURF: _build_turf(),
}


def get_matrix(methodology: Methodology) -> MethodologyMatrix:
    """Return the section matrix for a methodology."""
    return METHODOLOGY_MATRIX[methodology]


def get_all_methodologies() -> list[dict[str, Any]]:
    """Return a summary list suitable for a methodology selector UI."""
    return [
        {
            "value": m.methodology.value,
            "label": m.label,
            "description": m.description,
            "default_loi": list(m.default_loi_minutes),
        }
        for m in METHODOLOGY_MATRIX.values()
    ]


def validate_section_selection(methodology: Methodology, selected: list[str]) -> list[str]:
    """Return list of error messages if the selection is invalid."""
    matrix = METHODOLOGY_MATRIX[methodology]
    errors: list[str] = []
    valid_types = {st.value for st in matrix.section_order}

    for s in selected:
        if s not in valid_types:
            errors.append(f"Section '{s}' is not valid for methodology '{methodology.value}'.")

    for st in matrix.required_sections():
        if st.value not in selected:
            errors.append(f"Required section '{st.value}' is missing for methodology '{methodology.value}'.")

    return errors
