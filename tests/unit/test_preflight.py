"""Contract tests for generation preflight gate (P02-03).

AC-1: Preflight checks required fields before generation.
AC-2: UI clearly shows missing requirements.
AC-3: Assistant provides targeted prompts to fill missing context.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from packages.shared.assistant_context import Methodology
from packages.shared.brief_parser import BriefFields, parse_brief_fields
from packages.shared.preflight import (
    CheckStatus,
    PreflightResult,
    run_preflight,
)

client = TestClient(app)

COMPLETE_BRIEF = """
Research Objectives: Understand brand health for KIND Bars.
Target Audience: US adults 18-54 who purchase snack bars monthly.
Product Category: Premium snack bars
Geographic Scope: United States
Constraints: LOI max 15 minutes
"""

INCOMPLETE_BRIEF = """
Research Objectives: Test new product concepts.
"""

MINIMAL_BRIEF = "Just a sentence."


def _fields(text: str) -> BriefFields:
    return parse_brief_fields(text)


# ---------------------------------------------------------------------------
# AC-1: Preflight checks required fields before generation
# ---------------------------------------------------------------------------

class TestPreflightBlocking:
    def test_complete_brief_with_methodology_can_generate(self):
        result = run_preflight(_fields(COMPLETE_BRIEF), Methodology.SEGMENTATION)
        assert result.can_generate is True
        assert result.blocking_count == 0

    def test_incomplete_brief_cannot_generate(self):
        result = run_preflight(_fields(INCOMPLETE_BRIEF), Methodology.SEGMENTATION)
        assert result.can_generate is False
        assert result.blocking_count >= 3  # audience, category, geography

    def test_no_methodology_blocks_generation(self):
        result = run_preflight(_fields(COMPLETE_BRIEF), methodology=None)
        assert result.can_generate is False
        blocking_ids = {c.check_id for c in result.blocking_checks()}
        assert "methodology_selected" in blocking_ids

    def test_empty_brief_blocks_generation(self):
        fields = BriefFields(raw_text="")
        result = run_preflight(fields, Methodology.SEGMENTATION)
        assert result.can_generate is False
        assert result.blocking_count >= 5  # all fields + content

    def test_each_required_field_checked(self):
        result = run_preflight(_fields(COMPLETE_BRIEF), Methodology.SEGMENTATION)
        check_ids = {c.check_id for c in result.checks}
        assert "field_objectives" in check_ids
        assert "field_audience" in check_ids
        assert "field_category" in check_ids
        assert "field_geography" in check_ids
        assert "methodology_selected" in check_ids
        assert "brief_content" in check_ids

    def test_whitespace_only_field_treated_as_missing(self):
        fields = BriefFields(
            objectives="   ",
            audience="Real audience",
            category="Real category",
            geography="Real geography",
            raw_text="Enough content for the brief quality check to pass easily.",
        )
        result = run_preflight(fields, Methodology.SEGMENTATION)
        objectives_check = next(c for c in result.checks if c.check_id == "field_objectives")
        assert objectives_check.status == CheckStatus.FAIL


# ---------------------------------------------------------------------------
# AC-1 continued: Warning checks
# ---------------------------------------------------------------------------

class TestPreflightWarnings:
    def test_missing_constraints_is_warning_not_blocking(self):
        text = """
Research Objectives: Study brand health.
Target Audience: Adults 18-54.
Product Category: Snack bars.
Geographic Scope: United States.
"""
        result = run_preflight(_fields(text), Methodology.SEGMENTATION)
        assert result.can_generate is True  # warnings don't block
        assert result.warning_count >= 1
        constraints_check = next(c for c in result.checks if c.check_id == "field_constraints")
        assert constraints_check.status == CheckStatus.WARN

    def test_short_brief_content_is_warning(self):
        fields = BriefFields(
            objectives="Test",
            audience="Adults",
            category="Food",
            geography="US",
            raw_text="Short brief.",
        )
        result = run_preflight(fields, Methodology.SEGMENTATION)
        content_check = next(c for c in result.checks if c.check_id == "brief_content")
        assert content_check.status == CheckStatus.WARN


# ---------------------------------------------------------------------------
# AC-2: UI clearly shows missing requirements (for_ui output)
# ---------------------------------------------------------------------------

class TestUIOutput:
    def test_for_ui_returns_structured_list(self):
        result = run_preflight(_fields(INCOMPLETE_BRIEF), Methodology.SEGMENTATION)
        ui_data = result.for_ui()
        assert isinstance(ui_data, list)
        assert len(ui_data) >= 6

    def test_for_ui_has_required_keys(self):
        result = run_preflight(_fields(INCOMPLETE_BRIEF), Methodology.SEGMENTATION)
        for item in result.for_ui():
            assert "check_id" in item
            assert "label" in item
            assert "status" in item
            assert "message" in item
            assert "assistant_prompt" in item

    def test_failing_checks_have_clear_messages(self):
        result = run_preflight(_fields(INCOMPLETE_BRIEF), Methodology.SEGMENTATION)
        for check in result.blocking_checks():
            assert "required" in check.message.lower() or "not provided" in check.message.lower() or "no " in check.message.lower()
            assert check.label  # human-readable label

    def test_passing_checks_show_positive_message(self):
        result = run_preflight(_fields(COMPLETE_BRIEF), Methodology.SEGMENTATION)
        for check in result.checks:
            if check.status == CheckStatus.PASS:
                assert "provided" in check.message.lower() or "selected" in check.message.lower() or "sufficient" in check.message.lower()


# ---------------------------------------------------------------------------
# AC-3: Assistant provides targeted prompts
# ---------------------------------------------------------------------------

class TestAssistantPrompts:
    def test_failing_checks_have_prompts(self):
        result = run_preflight(_fields(INCOMPLETE_BRIEF), methodology=None)
        for check in result.blocking_checks():
            assert check.assistant_prompt is not None
            assert len(check.assistant_prompt) > 10

    def test_warning_checks_have_prompts(self):
        result = run_preflight(_fields(INCOMPLETE_BRIEF), Methodology.SEGMENTATION)
        for check in result.warning_checks():
            assert check.assistant_prompt is not None

    def test_passing_checks_have_no_prompts(self):
        result = run_preflight(_fields(COMPLETE_BRIEF), Methodology.SEGMENTATION)
        for check in result.checks:
            if check.status == CheckStatus.PASS:
                assert check.assistant_prompt is None

    def test_prompts_are_specific_to_field(self):
        result = run_preflight(_fields(INCOMPLETE_BRIEF), Methodology.SEGMENTATION)
        audience_check = next(c for c in result.checks if c.check_id == "field_audience")
        assert audience_check.assistant_prompt is not None
        assert "respondent" in audience_check.assistant_prompt.lower() or "survey" in audience_check.assistant_prompt.lower() or "who" in audience_check.assistant_prompt.lower()

    def test_methodology_prompt_lists_options(self):
        result = run_preflight(_fields(COMPLETE_BRIEF), methodology=None)
        meth_check = next(c for c in result.checks if c.check_id == "methodology_selected")
        assert meth_check.assistant_prompt is not None
        assert "segmentation" in meth_check.assistant_prompt.lower()


# ---------------------------------------------------------------------------
# API integration
# ---------------------------------------------------------------------------

class TestPreflightAPI:
    def _upload(self, text: str) -> str:
        resp = client.post(
            "/api/v1/briefs/upload?project_id=proj-001",
            files={"file": ("brief.md", text.encode("utf-8"), "text/markdown")},
        )
        return resp.json()["brief_id"]

    def test_preflight_endpoint_complete(self):
        brief_id = self._upload(COMPLETE_BRIEF)
        resp = client.get(f"/api/v1/preflight/{brief_id}?methodology=segmentation")
        assert resp.status_code == 200
        body = resp.json()
        assert body["can_generate"] is True
        assert body["blocking_count"] == 0

    def test_preflight_endpoint_incomplete(self):
        brief_id = self._upload(INCOMPLETE_BRIEF)
        resp = client.get(f"/api/v1/preflight/{brief_id}?methodology=segmentation")
        assert resp.status_code == 200
        body = resp.json()
        assert body["can_generate"] is False
        assert body["blocking_count"] >= 3

    def test_preflight_no_methodology(self):
        brief_id = self._upload(COMPLETE_BRIEF)
        resp = client.get(f"/api/v1/preflight/{brief_id}")
        assert resp.status_code == 200
        assert resp.json()["can_generate"] is False

    def test_preflight_bad_methodology(self):
        brief_id = self._upload(COMPLETE_BRIEF)
        resp = client.get(f"/api/v1/preflight/{brief_id}?methodology=fake")
        assert resp.status_code == 400

    def test_preflight_nonexistent_brief(self):
        resp = client.get("/api/v1/preflight/nonexistent?methodology=segmentation")
        assert resp.status_code == 404

    def test_preflight_checks_include_prompts(self):
        brief_id = self._upload(INCOMPLETE_BRIEF)
        resp = client.get(f"/api/v1/preflight/{brief_id}?methodology=segmentation")
        checks = resp.json()["checks"]
        failing = [c for c in checks if c["status"] == "fail"]
        for c in failing:
            assert c["assistant_prompt"] is not None
