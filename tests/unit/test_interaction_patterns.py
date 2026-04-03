"""Contract tests for AI-first interaction patterns (P00-03).

Verify:
1. Copilot panel behavior defined for every major screen.
2. Critical approval checkpoints documented.
3. Fallback manual paths documented for each AI-assisted action.
"""

from __future__ import annotations

import pytest

from packages.shared.interaction_patterns import (
    APPROVAL_CHECKPOINTS,
    COPILOT_PANELS,
    CopilotAction,
    FALLBACK_PATHS,
    PATTERNS_VERSION,
    ApprovalCheckpoint,
    CheckpointSeverity,
    CopilotPanelSpec,
    FallbackPath,
    Screen,
    check_fallback_action_coverage,
    get_all_screens_summary,
    get_checkpoints_for_screen,
    get_copilot_spec,
    get_fallback_for_screen,
)


# ---------------------------------------------------------------------------
# AC-1: Copilot panel behavior defined for every major screen
# ---------------------------------------------------------------------------

class TestCopilotCoverage:
    def test_every_screen_has_copilot_spec(self):
        for screen in Screen:
            assert screen in COPILOT_PANELS, f"Screen {screen.value} missing copilot spec"

    @pytest.mark.parametrize("screen", list(Screen))
    def test_copilot_spec_has_required_fields(self, screen: Screen):
        spec = COPILOT_PANELS[screen]
        assert isinstance(spec, CopilotPanelSpec)
        assert spec.screen == screen
        assert spec.workflow_stage is not None
        assert len(spec.available_actions) > 0
        assert spec.default_action in spec.available_actions
        assert spec.description

    @pytest.mark.parametrize("screen", list(Screen))
    def test_copilot_has_context_chips(self, screen: Screen):
        spec = COPILOT_PANELS[screen]
        assert isinstance(spec.context_chips, list)
        # At minimum project_name should be trackable
        # (not all screens require it in chips but the list should exist)

    @pytest.mark.parametrize("screen", list(Screen))
    def test_get_copilot_spec_helper(self, screen: Screen):
        spec = get_copilot_spec(screen)
        assert spec.screen == screen

    def test_total_screen_count(self):
        assert len(Screen) == 14
        assert len(COPILOT_PANELS) == 14


# ---------------------------------------------------------------------------
# AC-2: Critical approval checkpoints documented
# ---------------------------------------------------------------------------

REQUIRED_CHECKPOINTS = [
    "publish_draft",
    "lock_mapping",
    "run_analysis",
    "export_artifacts",
]


class TestApprovalCheckpoints:
    def test_four_critical_checkpoints_exist(self):
        ids = {cp.checkpoint_id for cp in APPROVAL_CHECKPOINTS}
        for required_id in REQUIRED_CHECKPOINTS:
            assert required_id in ids, f"Missing checkpoint: {required_id}"

    @pytest.mark.parametrize("checkpoint_id", REQUIRED_CHECKPOINTS)
    def test_checkpoint_has_required_fields(self, checkpoint_id: str):
        cp = next(c for c in APPROVAL_CHECKPOINTS if c.checkpoint_id == checkpoint_id)
        assert isinstance(cp, ApprovalCheckpoint)
        assert cp.label
        assert cp.screen is not None
        assert cp.severity is not None
        assert cp.description
        assert cp.rollback_path

    def test_publish_draft_is_blocking(self):
        cp = next(c for c in APPROVAL_CHECKPOINTS if c.checkpoint_id == "publish_draft")
        assert cp.severity == CheckpointSeverity.BLOCKING

    def test_lock_mapping_is_blocking(self):
        cp = next(c for c in APPROVAL_CHECKPOINTS if c.checkpoint_id == "lock_mapping")
        assert cp.severity == CheckpointSeverity.BLOCKING

    def test_run_analysis_is_blocking(self):
        cp = next(c for c in APPROVAL_CHECKPOINTS if c.checkpoint_id == "run_analysis")
        assert cp.severity == CheckpointSeverity.BLOCKING

    def test_publish_draft_requires_validation(self):
        cp = next(c for c in APPROVAL_CHECKPOINTS if c.checkpoint_id == "publish_draft")
        assert cp.requires_validation_pass is True

    def test_each_checkpoint_documents_what_gets_locked(self):
        for cp in APPROVAL_CHECKPOINTS:
            assert isinstance(cp.what_gets_locked, list)

    def test_each_checkpoint_documents_rollback(self):
        for cp in APPROVAL_CHECKPOINTS:
            assert cp.rollback_path, f"Checkpoint {cp.checkpoint_id} missing rollback_path"

    def test_get_checkpoints_for_screen(self):
        editor_cps = get_checkpoints_for_screen(Screen.QUESTIONNAIRE_EDITOR)
        assert any(cp.checkpoint_id == "publish_draft" for cp in editor_cps)

    def test_no_checkpoints_for_brief_upload(self):
        cps = get_checkpoints_for_screen(Screen.BRIEF_UPLOAD)
        assert len(cps) == 0


# ---------------------------------------------------------------------------
# AC-3: Fallback manual paths for each AI-assisted action
# ---------------------------------------------------------------------------

# Derived: every screen with a copilot panel has AI-assisted actions needing a fallback.
SCREENS_WITH_AI_ACTIONS = list(Screen)


class TestFallbackPaths:
    def test_fallback_exists_for_ai_action_screens(self):
        screens_with_fallback = {fp.screen for fp in FALLBACK_PATHS}
        for screen in SCREENS_WITH_AI_ACTIONS:
            assert screen in screens_with_fallback, f"Screen {screen.value} missing fallback path"

    @pytest.mark.parametrize("screen", SCREENS_WITH_AI_ACTIONS)
    def test_fallback_has_required_fields(self, screen: Screen):
        fallbacks = get_fallback_for_screen(screen)
        assert len(fallbacks) > 0
        for fb in fallbacks:
            assert isinstance(fb, FallbackPath)
            assert fb.ai_action
            assert fb.ai_action_type in CopilotAction  # Fix 3: typed action
            assert fb.manual_alternative
            assert len(fb.manual_steps) > 0

    def test_total_fallback_count(self):
        assert len(FALLBACK_PATHS) >= 14  # at least one per screen

    def test_get_fallback_helper(self):
        fallbacks = get_fallback_for_screen(Screen.MAPPING_EDITOR)
        assert len(fallbacks) > 0
        assert fallbacks[0].screen == Screen.MAPPING_EDITOR

    def test_action_level_coverage_complete(self):
        """Fix 3: every (screen, action) pair from COPILOT_PANELS must have a fallback."""
        result = check_fallback_action_coverage()
        assert len(result["missing"]) == 0, (
            f"Missing fallback coverage for {len(result['missing'])} action(s): {result['missing']}"
        )

    def test_coverage_helper_returns_counts(self):
        result = check_fallback_action_coverage()
        assert result["total_pairs"] > 0
        assert result["covered_count"] == result["total_pairs"]


# ---------------------------------------------------------------------------
# Summary / consumability
# ---------------------------------------------------------------------------

class TestConsumability:
    def test_get_all_screens_summary(self):
        summary = get_all_screens_summary()
        assert len(summary) == 14
        for entry in summary:
            assert "screen" in entry
            assert "workflow_stage" in entry
            assert "copilot_actions" in entry
            assert "has_checkpoint" in entry
            assert "has_fallback" in entry

    def test_screens_with_checkpoints_flagged(self):
        summary = get_all_screens_summary()
        editor = next(s for s in summary if s["screen"] == "questionnaire_editor")
        assert editor["has_checkpoint"] is True

    def test_screens_with_fallbacks_flagged(self):
        summary = get_all_screens_summary()
        mapping = next(s for s in summary if s["screen"] == "mapping_editor")
        assert mapping["has_fallback"] is True


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

class TestVersioning:
    def test_version_is_semver(self):
        parts = PATTERNS_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)
