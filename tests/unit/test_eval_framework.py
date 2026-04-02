"""Contract tests for evaluation framework (P00-04).

Verify:
1. Eval scenarios exist for brief grounding, section generation, mapping suggestions, analysis explanations.
2. Pass/fail thresholds are documented.
3. CI hooks for eval test execution are planned.
"""

from __future__ import annotations

import pytest

from packages.shared.assistant_context import WorkflowStage
from packages.shared.eval_framework import (
    CI_HOOKS,
    DIMENSION_THRESHOLDS,
    EVAL_FRAMEWORK_VERSION,
    EVAL_SCENARIOS,
    CIHook,
    DimensionThreshold,
    EvalDimension,
    EvalScenario,
    ScoreLevel,
    get_ci_hooks,
    get_critical_scenarios,
    get_eval_summary,
    get_scenarios_for_stage,
    get_threshold,
    score_result,
)

REQUIRED_STAGES = [
    WorkflowStage.BRIEF,
    WorkflowStage.QUESTIONNAIRE,
    WorkflowStage.MAPPING,
    WorkflowStage.TABLE_QA,
    WorkflowStage.ANALYSIS,
]


# ---------------------------------------------------------------------------
# AC-1: Eval scenarios for brief, generation, mapping, analysis
# ---------------------------------------------------------------------------

class TestScenarioCoverage:
    @pytest.mark.parametrize("stage", REQUIRED_STAGES)
    def test_stage_has_at_least_one_scenario(self, stage: WorkflowStage):
        scenarios = get_scenarios_for_stage(stage)
        assert len(scenarios) >= 1, f"No eval scenarios for stage {stage.value}"

    def test_brief_grounding_scenarios_exist(self):
        brief_scenarios = get_scenarios_for_stage(WorkflowStage.BRIEF)
        assert len(brief_scenarios) >= 2
        actions = {s.action for s in brief_scenarios}
        assert "summarize_brief" in actions
        assert "identify_gaps" in actions

    def test_section_generation_scenarios_exist(self):
        gen_scenarios = get_scenarios_for_stage(WorkflowStage.QUESTIONNAIRE)
        assert len(gen_scenarios) >= 2
        actions = {s.action for s in gen_scenarios}
        assert "generate_section" in actions

    def test_mapping_scenarios_exist(self):
        map_scenarios = get_scenarios_for_stage(WorkflowStage.MAPPING)
        assert len(map_scenarios) >= 1
        actions = {s.action for s in map_scenarios}
        assert "auto_map" in actions

    def test_analysis_explanation_scenarios_exist(self):
        analysis_scenarios = get_scenarios_for_stage(WorkflowStage.ANALYSIS)
        assert len(analysis_scenarios) >= 2
        actions = {s.action for s in analysis_scenarios}
        assert "explain_results" in actions

    def test_total_scenario_count(self):
        assert len(EVAL_SCENARIOS) >= 10

    def test_critical_scenarios_exist(self):
        critical = get_critical_scenarios()
        assert len(critical) >= 5

    @pytest.mark.parametrize("scenario", EVAL_SCENARIOS, ids=lambda s: s.scenario_id)
    def test_scenario_has_required_fields(self, scenario: EvalScenario):
        assert scenario.scenario_id
        assert scenario.stage is not None
        assert scenario.action
        assert scenario.description
        assert scenario.input_fixture
        assert len(scenario.expected_behavior) >= 1
        assert len(scenario.dimensions) >= 1

    @pytest.mark.parametrize("scenario", EVAL_SCENARIOS, ids=lambda s: s.scenario_id)
    def test_scenario_dimensions_are_valid(self, scenario: EvalScenario):
        for dim in scenario.dimensions:
            assert dim in EvalDimension

    def test_scenario_ids_are_unique(self):
        ids = [s.scenario_id for s in EVAL_SCENARIOS]
        assert len(ids) == len(set(ids))

    @pytest.mark.parametrize("scenario", EVAL_SCENARIOS, ids=lambda s: s.scenario_id)
    def test_fixture_path_is_documented(self, scenario: EvalScenario):
        """Fixture paths are stubs until the eval runner is built.
        This test ensures they follow a consistent naming convention."""
        assert scenario.input_fixture.startswith("fixtures/")
        assert "/" in scenario.input_fixture  # has at least one subdirectory


# ---------------------------------------------------------------------------
# AC-2: Pass/fail thresholds are documented
# ---------------------------------------------------------------------------

class TestThresholds:
    def test_every_dimension_has_threshold(self):
        for dim in EvalDimension:
            assert dim in DIMENSION_THRESHOLDS, f"Missing threshold for {dim.value}"

    @pytest.mark.parametrize("dim", list(EvalDimension))
    def test_threshold_has_required_fields(self, dim: EvalDimension):
        t = get_threshold(dim)
        assert isinstance(t, DimensionThreshold)
        assert t.description
        assert t.pass_criterion
        assert t.fail_criterion
        assert 0.0 <= t.marginal_threshold <= t.pass_threshold <= 1.0

    def test_hallucination_is_binary(self):
        t = get_threshold(EvalDimension.HALLUCINATION_RESISTANCE)
        assert t.pass_threshold == 1.0
        assert t.marginal_threshold == 1.0  # No marginal zone

    def test_score_result_pass(self):
        assert score_result(EvalDimension.USEFULNESS, 0.85) == ScoreLevel.PASS

    def test_score_result_marginal(self):
        assert score_result(EvalDimension.USEFULNESS, 0.7) == ScoreLevel.MARGINAL

    def test_score_result_fail(self):
        assert score_result(EvalDimension.USEFULNESS, 0.5) == ScoreLevel.FAIL

    def test_score_result_hallucination_binary(self):
        assert score_result(EvalDimension.HALLUCINATION_RESISTANCE, 1.0) == ScoreLevel.PASS
        assert score_result(EvalDimension.HALLUCINATION_RESISTANCE, 0.99) == ScoreLevel.FAIL

    def test_grounding_threshold_is_strict(self):
        t = get_threshold(EvalDimension.GROUNDING)
        assert t.pass_threshold == 1.0
        assert t.marginal_threshold == 0.9


# ---------------------------------------------------------------------------
# AC-3: CI hooks for eval test execution are planned
# ---------------------------------------------------------------------------

class TestCIHooks:
    def test_at_least_three_hooks_planned(self):
        assert len(CI_HOOKS) >= 3

    def test_pr_hook_exists(self):
        pr_hooks = [h for h in CI_HOOKS if h.trigger == "pull_request"]
        assert len(pr_hooks) >= 1
        assert pr_hooks[0].blocking is True

    def test_merge_hook_exists(self):
        merge_hooks = [h for h in CI_HOOKS if h.trigger == "merge_to_main"]
        assert len(merge_hooks) >= 1

    def test_nightly_hook_exists(self):
        nightly_hooks = [h for h in CI_HOOKS if h.trigger == "scheduled_nightly"]
        assert len(nightly_hooks) >= 1

    def test_pr_hook_runs_only_critical_scenarios(self):
        pr_hook = next(h for h in CI_HOOKS if h.trigger == "pull_request")
        critical_ids = {s.scenario_id for s in get_critical_scenarios()}
        assert set(pr_hook.scenarios) == critical_ids

    def test_full_hooks_cover_all_scenarios(self):
        merge_hook = next(h for h in CI_HOOKS if h.trigger == "merge_to_main")
        all_ids = {s.scenario_id for s in EVAL_SCENARIOS}
        assert set(merge_hook.scenarios) == all_ids

    @pytest.mark.parametrize("hook", CI_HOOKS, ids=lambda h: h.hook_id)
    def test_hook_has_required_fields(self, hook: CIHook):
        assert hook.hook_id
        assert hook.trigger
        assert hook.description
        assert len(hook.scenarios) >= 1

    def test_get_ci_hooks_helper(self):
        hooks = get_ci_hooks()
        assert len(hooks) >= 3
        for h in hooks:
            assert "hook_id" in h
            assert "trigger" in h
            assert "scenario_count" in h
            assert "blocking" in h


# ---------------------------------------------------------------------------
# Summary / consumability
# ---------------------------------------------------------------------------

class TestConsumability:
    def test_get_eval_summary(self):
        summary = get_eval_summary()
        assert summary["version"] == EVAL_FRAMEWORK_VERSION
        assert summary["total_scenarios"] >= 10
        assert summary["critical_scenarios"] >= 5
        assert summary["dimensions"] == 6
        assert summary["ci_hooks"] >= 3
        assert set(REQUIRED_STAGES).issubset(
            {WorkflowStage(s) for s in summary["stages_covered"]}
        )


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

class TestVersioning:
    def test_version_is_semver(self):
        parts = EVAL_FRAMEWORK_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)
