"""Evaluation framework for assistant quality and grounding v1.

Defines eval scenarios, scoring dimensions, pass/fail thresholds,
and CI integration hooks for every assistant-facing workflow stage.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .assistant_context import WorkflowStage

EVAL_FRAMEWORK_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Scoring dimensions — what we measure on every assistant output
# ---------------------------------------------------------------------------

class EvalDimension(str, Enum):
    GROUNDING = "grounding"                # Output references actual input data
    CONSISTENCY = "consistency"            # No contradictions within output
    HALLUCINATION_RESISTANCE = "hallucination_resistance"  # No fabricated facts/numbers
    USEFULNESS = "usefulness"              # Output is actionable for the user
    COMPLETENESS = "completeness"          # All required elements present
    FORMAT_COMPLIANCE = "format_compliance"  # Output matches expected schema/structure


class ScoreLevel(str, Enum):
    PASS = "pass"
    MARGINAL = "marginal"
    FAIL = "fail"


# ---------------------------------------------------------------------------
# Thresholds — documented pass/fail criteria per dimension
# ---------------------------------------------------------------------------

class DimensionThreshold(BaseModel):
    """Pass/fail threshold for one evaluation dimension."""

    dimension: EvalDimension
    description: str
    pass_criterion: str
    marginal_criterion: str
    fail_criterion: str
    score_range: tuple[float, float] = (0.0, 1.0)
    pass_threshold: float
    marginal_threshold: float


DIMENSION_THRESHOLDS: dict[EvalDimension, DimensionThreshold] = {
    EvalDimension.GROUNDING: DimensionThreshold(
        dimension=EvalDimension.GROUNDING,
        description="Every claim in the output traces to a specific input element.",
        pass_criterion="100% of factual claims reference an identifiable input field, document section, or data value.",
        marginal_criterion="90-99% of claims are grounded; minor claims lack explicit source.",
        fail_criterion="<90% grounded, or any numeric claim is ungrounded.",
        pass_threshold=1.0,
        marginal_threshold=0.9,
    ),
    EvalDimension.CONSISTENCY: DimensionThreshold(
        dimension=EvalDimension.CONSISTENCY,
        description="No internal contradictions within the output.",
        pass_criterion="Zero contradictions between statements in the same output.",
        marginal_criterion="One minor inconsistency in non-critical detail.",
        fail_criterion="Any contradiction in key findings, numbers, or recommendations.",
        pass_threshold=1.0,
        marginal_threshold=0.95,
    ),
    EvalDimension.HALLUCINATION_RESISTANCE: DimensionThreshold(
        dimension=EvalDimension.HALLUCINATION_RESISTANCE,
        description="No fabricated facts, statistics, or entities.",
        pass_criterion="Zero fabricated elements. All numbers, names, and categories exist in inputs.",
        marginal_criterion="N/A — hallucination is binary pass/fail.",
        fail_criterion="Any fabricated statistic, entity name, or factual claim not in inputs.",
        pass_threshold=1.0,
        marginal_threshold=1.0,  # No marginal zone — binary
    ),
    EvalDimension.USEFULNESS: DimensionThreshold(
        dimension=EvalDimension.USEFULNESS,
        description="Output is actionable and relevant to the user's task.",
        pass_criterion="User can act on the output without additional research. Recommendations are specific.",
        marginal_criterion="Output is relevant but vague or requires follow-up questions.",
        fail_criterion="Output is generic, off-topic, or requires complete rework.",
        pass_threshold=0.8,
        marginal_threshold=0.6,
    ),
    EvalDimension.COMPLETENESS: DimensionThreshold(
        dimension=EvalDimension.COMPLETENESS,
        description="All required output elements are present.",
        pass_criterion="100% of required fields/sections present per the output schema.",
        marginal_criterion="90-99% of required fields present; missing fields are non-critical.",
        fail_criterion="<90% of required fields, or any critical field missing.",
        pass_threshold=1.0,
        marginal_threshold=0.9,
    ),
    EvalDimension.FORMAT_COMPLIANCE: DimensionThreshold(
        dimension=EvalDimension.FORMAT_COMPLIANCE,
        description="Output matches expected schema and structural requirements.",
        pass_criterion="Output parses without error against the target schema.",
        marginal_criterion="Output parses with minor fixable deviations.",
        fail_criterion="Output does not parse or has structural errors.",
        pass_threshold=1.0,
        marginal_threshold=0.9,
    ),
}


# ---------------------------------------------------------------------------
# Eval scenarios — concrete test cases per workflow stage
# ---------------------------------------------------------------------------

class EvalScenario(BaseModel):
    """One evaluation test case for a specific assistant action."""

    scenario_id: str
    stage: WorkflowStage
    action: str
    description: str
    input_fixture: str
    expected_behavior: list[str]
    dimensions: list[EvalDimension]
    critical: bool = False  # If True, failure blocks release


EVAL_SCENARIOS: list[EvalScenario] = [
    # --- Brief Grounding ---
    EvalScenario(
        scenario_id="EVAL-BRIEF-01",
        stage=WorkflowStage.BRIEF,
        action="summarize_brief",
        description="Summarize a CPG brand health research brief and extract structured fields.",
        input_fixture="fixtures/briefs/cpg_brand_health.md",
        expected_behavior=[
            "Summary references specific objectives from the brief.",
            "Extracted audience matches brief verbatim or is a faithful paraphrase.",
            "Category is correctly identified.",
            "No invented constraints or objectives.",
        ],
        dimensions=[
            EvalDimension.GROUNDING,
            EvalDimension.HALLUCINATION_RESISTANCE,
            EvalDimension.COMPLETENESS,
        ],
        critical=True,
    ),
    EvalScenario(
        scenario_id="EVAL-BRIEF-02",
        stage=WorkflowStage.BRIEF,
        action="identify_gaps",
        description="Identify missing fields in an incomplete brief.",
        input_fixture="fixtures/briefs/incomplete_brief.md",
        expected_behavior=[
            "Correctly identifies missing audience definition.",
            "Correctly identifies missing geography.",
            "Does not flag fields that are present as missing.",
            "Proposed assumptions are reasonable and labeled as assumptions.",
        ],
        dimensions=[
            EvalDimension.GROUNDING,
            EvalDimension.HALLUCINATION_RESISTANCE,
            EvalDimension.USEFULNESS,
        ],
        critical=True,
    ),
    # --- Section Generation ---
    EvalScenario(
        scenario_id="EVAL-GEN-01",
        stage=WorkflowStage.QUESTIONNAIRE,
        action="generate_section",
        description="Generate a screener section for a segmentation study.",
        input_fixture="fixtures/generation/segmentation_screener_context.json",
        expected_behavior=[
            "Output contains 3-6 screener questions.",
            "At least one termination rule is defined.",
            "Variable IDs follow naming convention.",
            "Response codes are exhaustive and mutually exclusive.",
            "Questions reference the target audience from the brief.",
        ],
        dimensions=[
            EvalDimension.GROUNDING,
            EvalDimension.FORMAT_COMPLIANCE,
            EvalDimension.COMPLETENESS,
        ],
        critical=True,
    ),
    EvalScenario(
        scenario_id="EVAL-GEN-02",
        stage=WorkflowStage.QUESTIONNAIRE,
        action="generate_section",
        description="Generate an attitudinal battery for a segmentation study.",
        input_fixture="fixtures/generation/segmentation_attitudes_context.json",
        expected_behavior=[
            "Output contains 20-40 Likert-scale items.",
            "All items use the same scale (5-point or 7-point).",
            "Items span multiple conceptual dimensions.",
            "Variable prefix is consistent (e.g., ATT_01, ATT_02).",
            "No duplicate or near-duplicate statements.",
        ],
        dimensions=[
            EvalDimension.FORMAT_COMPLIANCE,
            EvalDimension.COMPLETENESS,
            EvalDimension.CONSISTENCY,
        ],
        critical=True,
    ),
    EvalScenario(
        scenario_id="EVAL-GEN-03",
        stage=WorkflowStage.QUESTIONNAIRE,
        action="regenerate_section",
        description="Regenerate one section without altering others.",
        input_fixture="fixtures/generation/regenerate_one_section_context.json",
        expected_behavior=[
            "Only the targeted section changes.",
            "Other sections remain byte-identical.",
            "Change explanation references the user's edit request.",
        ],
        dimensions=[
            EvalDimension.CONSISTENCY,
            EvalDimension.GROUNDING,
            EvalDimension.USEFULNESS,
        ],
        critical=False,
    ),
    # --- Mapping Suggestions ---
    EvalScenario(
        scenario_id="EVAL-MAP-01",
        stage=WorkflowStage.MAPPING,
        action="auto_map",
        description="Auto-map data columns to questionnaire variables.",
        input_fixture="fixtures/mapping/clean_data_profile.json",
        expected_behavior=[
            "High-confidence mappings (>0.9) are correct for exact column name matches.",
            "Low-confidence mappings are flagged with explanation.",
            "Unmapped columns are listed separately.",
            "No questionnaire variable is mapped to two data columns.",
        ],
        dimensions=[
            EvalDimension.GROUNDING,
            EvalDimension.HALLUCINATION_RESISTANCE,
            EvalDimension.USEFULNESS,
        ],
        critical=True,
    ),
    EvalScenario(
        scenario_id="EVAL-MAP-02",
        stage=WorkflowStage.MAPPING,
        action="explain_low_confidence",
        description="Explain why a mapping has low confidence.",
        input_fixture="fixtures/mapping/ambiguous_columns.json",
        expected_behavior=[
            "Explanation references the specific column name and questionnaire variable.",
            "Reason for low confidence is stated (e.g., name mismatch, type mismatch).",
            "Suggested fix is actionable.",
        ],
        dimensions=[
            EvalDimension.GROUNDING,
            EvalDimension.USEFULNESS,
        ],
        critical=False,
    ),
    # --- Analysis Explanations ---
    EvalScenario(
        scenario_id="EVAL-ANALYSIS-01",
        stage=WorkflowStage.ANALYSIS,
        action="explain_results",
        description="Generate narrative for K-Means clustering output.",
        input_fixture="fixtures/analysis/kmeans_output.json",
        expected_behavior=[
            "Every numeric claim traces to a value in the output tables.",
            "Segment names/descriptions are derived from profile data, not invented.",
            "No unsupported causal claims.",
            "Key differences between segments are highlighted.",
        ],
        dimensions=[
            EvalDimension.GROUNDING,
            EvalDimension.HALLUCINATION_RESISTANCE,
            EvalDimension.USEFULNESS,
            EvalDimension.CONSISTENCY,
        ],
        critical=True,
    ),
    EvalScenario(
        scenario_id="EVAL-ANALYSIS-02",
        stage=WorkflowStage.ANALYSIS,
        action="explain_results",
        description="Generate narrative for driver analysis (regression) output.",
        input_fixture="fixtures/analysis/drivers_output.json",
        expected_behavior=[
            "Top drivers are correctly ranked by coefficient magnitude.",
            "Significance levels are reported accurately.",
            "R-squared is reported from the actual output.",
            "No fabricated variable names or coefficient values.",
        ],
        dimensions=[
            EvalDimension.GROUNDING,
            EvalDimension.HALLUCINATION_RESISTANCE,
            EvalDimension.CONSISTENCY,
        ],
        critical=True,
    ),
    EvalScenario(
        scenario_id="EVAL-ANALYSIS-03",
        stage=WorkflowStage.ANALYSIS,
        action="compare_runs",
        description="Compare two analysis runs and explain differences.",
        input_fixture="fixtures/analysis/run_comparison.json",
        expected_behavior=[
            "Input version differences are identified.",
            "Key metric deltas are computed correctly.",
            "Explanation of likely causes references the input changes.",
        ],
        dimensions=[
            EvalDimension.GROUNDING,
            EvalDimension.CONSISTENCY,
            EvalDimension.USEFULNESS,
        ],
        critical=False,
    ),
    # --- Table QA ---
    # TODO: REPORTING stage scenarios deferred to P08-01 (insight copilot) sprint item.
    EvalScenario(
        scenario_id="EVAL-QA-01",
        stage=WorkflowStage.TABLE_QA,
        action="explain_qa_finding",
        description="Explain a low-base-size QA finding and suggest remediation.",
        input_fixture="fixtures/qa/low_base_finding.json",
        expected_behavior=[
            "Explanation identifies the specific table and cell.",
            "Base size threshold is stated.",
            "Suggested action is one of: suppress cell, merge segments, flag in footnote.",
            "No fabricated base sizes.",
        ],
        dimensions=[
            EvalDimension.GROUNDING,
            EvalDimension.HALLUCINATION_RESISTANCE,
            EvalDimension.USEFULNESS,
        ],
        critical=False,
    ),
]


# ---------------------------------------------------------------------------
# CI integration plan
# ---------------------------------------------------------------------------

class CIHook(BaseModel):
    """Planned CI integration for eval execution."""

    hook_id: str
    trigger: str
    description: str
    scenarios: list[str]  # scenario_ids
    blocking: bool  # If True, CI fails on eval failure


CI_HOOKS: list[CIHook] = [
    CIHook(
        hook_id="ci-eval-critical",
        trigger="pull_request",
        description="Run all critical eval scenarios on every PR that touches assistant-facing code.",
        scenarios=[s.scenario_id for s in EVAL_SCENARIOS if s.critical],
        blocking=True,
    ),
    CIHook(
        hook_id="ci-eval-full",
        trigger="merge_to_main",
        description="Run full eval suite on merge to main. Failures block merge to prevent regressions.",
        scenarios=[s.scenario_id for s in EVAL_SCENARIOS],
        blocking=True,
    ),
    CIHook(
        hook_id="ci-eval-nightly",
        trigger="scheduled_nightly",
        description="Nightly full eval with regression tracking. Results stored for trend analysis.",
        scenarios=[s.scenario_id for s in EVAL_SCENARIOS],
        blocking=False,
    ),
]


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def get_scenarios_for_stage(stage: WorkflowStage) -> list[EvalScenario]:
    """Return all eval scenarios for a workflow stage."""
    return [s for s in EVAL_SCENARIOS if s.stage == stage]


def get_critical_scenarios() -> list[EvalScenario]:
    """Return all scenarios that block release on failure."""
    return [s for s in EVAL_SCENARIOS if s.critical]


def get_threshold(dimension: EvalDimension) -> DimensionThreshold:
    """Return the threshold spec for a scoring dimension."""
    return DIMENSION_THRESHOLDS[dimension]


def score_result(dimension: EvalDimension, score: float) -> ScoreLevel:
    """Classify a numeric score as pass/marginal/fail."""
    threshold = DIMENSION_THRESHOLDS[dimension]
    if score >= threshold.pass_threshold:
        return ScoreLevel.PASS
    if score >= threshold.marginal_threshold:
        return ScoreLevel.MARGINAL
    return ScoreLevel.FAIL


def get_ci_hooks() -> list[dict[str, Any]]:
    """Return CI hook specs for pipeline configuration."""
    return [
        {
            "hook_id": h.hook_id,
            "trigger": h.trigger,
            "description": h.description,
            "scenario_count": len(h.scenarios),
            "blocking": h.blocking,
        }
        for h in CI_HOOKS
    ]


def get_eval_summary() -> dict[str, Any]:
    """Return a summary of the eval framework for documentation/dashboards."""
    return {
        "version": EVAL_FRAMEWORK_VERSION,
        "total_scenarios": len(EVAL_SCENARIOS),
        "critical_scenarios": len(get_critical_scenarios()),
        "dimensions": len(EvalDimension),
        "ci_hooks": len(CI_HOOKS),
        "stages_covered": sorted({s.stage.value for s in EVAL_SCENARIOS}),
    }
