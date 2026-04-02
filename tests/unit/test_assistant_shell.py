"""Contract tests for global assistant shell (P01-03).

AC-1: Assistant panel visible across all app stages.
AC-2: Context chips display active brief/methodology/versions.
AC-3: Assistant invocation logs include context hash.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from packages.shared.assistant_context import (
    AssistantContext,
    BriefContext,
    MappingVersionRef,
    Methodology,
    QuestionnaireVersionRef,
    RunMetadata,
    WorkflowStage,
)
from packages.shared.assistant_shell import (
    InvocationLog,
    InvocationRecord,
    PanelState,
    build_context_chips,
    compute_context_hash,
    get_panel_state,
)
from packages.shared.interaction_patterns import CopilotAction, Screen

client = TestClient(app)
NOW = datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_ctx() -> AssistantContext:
    return AssistantContext(
        project_id="proj-001",
        stage=WorkflowStage.BRIEF,
        methodology=Methodology.SEGMENTATION,
    )


def _full_ctx() -> AssistantContext:
    return AssistantContext(
        project_id="proj-001",
        stage=WorkflowStage.ANALYSIS,
        methodology=Methodology.SEGMENTATION,
        brief=BriefContext(
            brief_id="brief-001",
            objectives="Understand brand health for KIND Bars",
            audience="US adults 18-54",
            category="snack bars",
            uploaded_at=NOW,
        ),
        selected_sections=["screener", "attitudes", "demographics"],
        questionnaire_ref=QuestionnaireVersionRef(
            questionnaire_id="qre-001",
            version=3,
            section_ids=["screener", "attitudes", "demographics"],
        ),
        mapping_ref=MappingVersionRef(
            mapping_id="map-001",
            version=2,
            data_file_hash="sha256:abcdef1234567890",
        ),
        run_metadata=RunMetadata(
            run_id="run-042",
            run_type="kmeans",
            started_at=NOW,
            questionnaire_version=3,
            mapping_version=2,
        ),
    )


# ---------------------------------------------------------------------------
# AC-1: Panel visible across all app stages
# ---------------------------------------------------------------------------

class TestPanelCoverage:
    @pytest.mark.parametrize("screen", list(Screen))
    def test_get_panel_state_works_for_every_screen(self, screen: Screen):
        ctx = _minimal_ctx()
        state = get_panel_state(ctx, screen)
        assert isinstance(state, PanelState)
        assert state.screen == screen
        assert len(state.available_actions) > 0
        assert state.default_action in state.available_actions
        assert state.context_hash

    @pytest.mark.parametrize("screen", list(Screen))
    def test_panel_state_includes_context_chips(self, screen: Screen):
        ctx = _minimal_ctx()
        state = get_panel_state(ctx, screen)
        assert len(state.context_chips) >= 3  # project, methodology, stage at minimum

    def test_panel_state_checkpoint_flagged_on_editor(self):
        ctx = _minimal_ctx()
        state = get_panel_state(ctx, Screen.QUESTIONNAIRE_EDITOR)
        assert state.has_checkpoint is True
        assert len(state.checkpoints) > 0

    def test_panel_state_no_checkpoint_on_brief(self):
        ctx = _minimal_ctx()
        state = get_panel_state(ctx, Screen.BRIEF_UPLOAD)
        assert state.has_checkpoint is False


# ---------------------------------------------------------------------------
# AC-2: Context chips display active brief/methodology/versions
# ---------------------------------------------------------------------------

class TestContextChips:
    def test_minimal_context_has_base_chips(self):
        chips = build_context_chips(_minimal_ctx())
        keys = {c.key for c in chips}
        assert "project" in keys
        assert "methodology" in keys
        assert "stage" in keys

    def test_full_context_has_all_chips(self):
        chips = build_context_chips(_full_ctx())
        keys = {c.key for c in chips}
        assert "project" in keys
        assert "methodology" in keys
        assert "stage" in keys
        assert "brief" in keys
        assert "questionnaire" in keys
        assert "mapping" in keys
        assert "run" in keys

    def test_chip_values_are_correct(self):
        ctx = _full_ctx()
        chips = {c.key: c for c in build_context_chips(ctx)}
        assert chips["project"].value == "proj-001"
        assert chips["methodology"].value == "segmentation"
        assert chips["questionnaire"].value == "v3"
        assert chips["mapping"].value == "v2"
        assert chips["run"].value == "run-042"
        assert chips["brief"].value == "brief-001"

    def test_brief_chip_has_tooltip(self):
        chips = {c.key: c for c in build_context_chips(_full_ctx())}
        assert chips["brief"].tooltip is not None
        assert "KIND Bars" in chips["brief"].tooltip

    def test_mapping_chip_has_data_hash_tooltip(self):
        chips = {c.key: c for c in build_context_chips(_full_ctx())}
        assert chips["mapping"].tooltip is not None
        assert "sha256:" in chips["mapping"].tooltip


# ---------------------------------------------------------------------------
# AC-3: Invocation logs include context hash
# ---------------------------------------------------------------------------

class TestInvocationLog:
    def test_record_creates_entry_with_context_hash(self):
        log = InvocationLog()
        ctx = _minimal_ctx()
        record = log.record(
            invocation_id="inv-001",
            ctx=ctx,
            screen=Screen.BRIEF_UPLOAD,
            action=CopilotAction.SUGGEST,
            input_summary="Summarize brief",
        )
        assert record.context_hash == compute_context_hash(ctx)
        assert record.status == "pending"
        assert record.invocation_id == "inv-001"

    def test_complete_marks_done(self):
        log = InvocationLog()
        log.record(
            invocation_id="inv-002",
            ctx=_minimal_ctx(),
            screen=Screen.BRIEF_REVIEW,
            action=CopilotAction.SUMMARIZE,
            input_summary="Summarize brief",
        )
        log.complete("inv-002", output_summary="Brief summarized", duration_ms=450)
        records = log.get_by_project("proj-001")
        assert records[0].status == "completed"
        assert records[0].duration_ms == 450

    def test_fail_marks_failed(self):
        log = InvocationLog()
        log.record(
            invocation_id="inv-003",
            ctx=_minimal_ctx(),
            screen=Screen.QUESTIONNAIRE_EDITOR,
            action=CopilotAction.GENERATE,
            input_summary="Generate screener",
        )
        log.fail("inv-003", error="LLM timeout")
        records = log.get_by_project("proj-001")
        assert records[0].status == "failed"
        assert "LLM timeout" in records[0].output_summary

    def test_get_by_project_filters(self):
        log = InvocationLog()
        ctx_a = AssistantContext(
            project_id="proj-a", stage=WorkflowStage.BRIEF, methodology=Methodology.SEGMENTATION,
        )
        ctx_b = AssistantContext(
            project_id="proj-b", stage=WorkflowStage.BRIEF, methodology=Methodology.MAXDIFF,
        )
        log.record(invocation_id="inv-a1", ctx=ctx_a, screen=Screen.BRIEF_UPLOAD, action=CopilotAction.SUGGEST, input_summary="a1")
        log.record(invocation_id="inv-b1", ctx=ctx_b, screen=Screen.BRIEF_UPLOAD, action=CopilotAction.SUGGEST, input_summary="b1")
        assert len(log.get_by_project("proj-a")) == 1
        assert len(log.get_by_project("proj-b")) == 1

    def test_get_by_context_hash(self):
        log = InvocationLog()
        ctx = _minimal_ctx()
        log.record(invocation_id="inv-h1", ctx=ctx, screen=Screen.BRIEF_UPLOAD, action=CopilotAction.SUGGEST, input_summary="h1")
        log.record(invocation_id="inv-h2", ctx=ctx, screen=Screen.BRIEF_REVIEW, action=CopilotAction.SUMMARIZE, input_summary="h2")
        ctx_hash = compute_context_hash(ctx)
        assert len(log.get_by_context_hash(ctx_hash)) == 2

    def test_count(self):
        log = InvocationLog()
        assert log.count == 0
        log.record(invocation_id="inv-c1", ctx=_minimal_ctx(), screen=Screen.BRIEF_UPLOAD, action=CopilotAction.SUGGEST, input_summary="c1")
        assert log.count == 1

    def test_complete_unknown_raises(self):
        log = InvocationLog()
        with pytest.raises(ValueError, match="not found"):
            log.complete("nonexistent", output_summary="x", duration_ms=0)

    def test_fail_unknown_raises(self):
        log = InvocationLog()
        with pytest.raises(ValueError, match="not found"):
            log.fail("nonexistent", error="x")


# ---------------------------------------------------------------------------
# Context hashing
# ---------------------------------------------------------------------------

class TestContextHash:
    def test_hash_is_deterministic(self):
        ctx = _full_ctx()
        h1 = compute_context_hash(ctx)
        h2 = compute_context_hash(ctx)
        assert h1 == h2

    def test_hash_changes_with_context(self):
        ctx1 = _minimal_ctx()
        ctx2 = AssistantContext(
            project_id="proj-002",
            stage=WorkflowStage.BRIEF,
            methodology=Methodology.SEGMENTATION,
        )
        assert compute_context_hash(ctx1) != compute_context_hash(ctx2)

    def test_hash_is_16_hex_chars(self):
        h = compute_context_hash(_minimal_ctx())
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

class TestAssistantAPI:
    def test_panel_state_endpoint(self):
        ctx = _minimal_ctx()
        resp = client.post(
            "/api/v1/assistant/panel-state?screen=brief_upload",
            json=ctx.model_dump(mode="json"),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["screen"] == "brief_upload"
        assert len(body["context_chips"]) >= 3
        assert body["context_hash"]

    def test_context_chips_endpoint(self):
        ctx = _full_ctx()
        resp = client.post(
            "/api/v1/assistant/context-chips",
            json=ctx.model_dump(mode="json"),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["chips"]) >= 7

    def test_context_hash_endpoint(self):
        ctx = _minimal_ctx()
        resp = client.post(
            "/api/v1/assistant/context-hash",
            json=ctx.model_dump(mode="json"),
        )
        assert resp.status_code == 200
        assert len(resp.json()["context_hash"]) == 16

    def test_panel_state_bad_screen_returns_400(self):
        ctx = _minimal_ctx()
        resp = client.post(
            "/api/v1/assistant/panel-state?screen=fake_screen",
            json=ctx.model_dump(mode="json"),
        )
        assert resp.status_code == 400
