"""Contract tests for brief analyzer assistant mode (P02-02).

AC-1: Assistant output references brief content directly.
AC-2: User can accept/reject each assumption.
AC-3: Accepted assumptions become part of generation context.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from packages.shared.brief_analyzer import (
    AssumptionStatus,
    BriefAnalysis,
    analyze_brief,
    apply_accepted_assumptions,
    resolve_assumption,
)
from packages.shared.brief_parser import BriefFields, parse_brief_fields

client = TestClient(app)

COMPLETE_BRIEF = """
Research Objectives: Understand brand health for KIND Bars among premium snack bar consumers.
Target Audience: US adults 18-54 who purchase snack bars monthly.
Product Category: Premium snack bars
Geographic Scope: United States
Constraints: LOI max 15 minutes, n=1000
"""

INCOMPLETE_BRIEF = """
Research Objectives: Test new product concepts for market viability.
"""

MINIMAL_BRIEF = """
Purpose: Explore consumer attitudes.
"""


def _fields(text: str) -> BriefFields:
    return parse_brief_fields(text)


# ---------------------------------------------------------------------------
# AC-1: Assistant output references brief content directly
# ---------------------------------------------------------------------------

class TestSummaryGrounding:
    def test_summary_references_objectives(self):
        fields = _fields(COMPLETE_BRIEF)
        analysis = analyze_brief("brief-001", fields)
        assert "KIND Bars" in analysis.summary

    def test_summary_references_audience(self):
        fields = _fields(COMPLETE_BRIEF)
        analysis = analyze_brief("brief-001", fields)
        assert "18-54" in analysis.summary

    def test_summary_references_category(self):
        fields = _fields(COMPLETE_BRIEF)
        analysis = analyze_brief("brief-001", fields)
        assert "snack bar" in analysis.summary.lower()

    def test_summary_references_geography(self):
        fields = _fields(COMPLETE_BRIEF)
        analysis = analyze_brief("brief-001", fields)
        assert "United States" in analysis.summary

    def test_incomplete_brief_summary_includes_available_content(self):
        fields = _fields(INCOMPLETE_BRIEF)
        analysis = analyze_brief("brief-002", fields)
        assert "concept" in analysis.summary.lower() or "market" in analysis.summary.lower()

    def test_assumption_source_references_brief_content(self):
        fields = _fields(INCOMPLETE_BRIEF)
        analysis = analyze_brief("brief-002", fields)
        for a in analysis.assumptions:
            assert len(a.source_reference) > 0
            # Source reference should mention what IS in the brief
            assert "objectives" in a.source_reference.lower() or "brief" in a.source_reference.lower()

    def test_empty_brief_handled_gracefully(self):
        fields = BriefFields(raw_text="nothing useful here")
        analysis = analyze_brief("brief-empty", fields)
        assert "empty" in analysis.summary.lower() or "all required" in analysis.summary.lower()


# ---------------------------------------------------------------------------
# AC-1 continued: Gap identification
# ---------------------------------------------------------------------------

class TestGapIdentification:
    def test_complete_brief_has_no_gaps(self):
        fields = _fields(COMPLETE_BRIEF)
        analysis = analyze_brief("brief-001", fields)
        assert len(analysis.gaps) == 0

    def test_incomplete_brief_identifies_missing_fields(self):
        fields = _fields(INCOMPLETE_BRIEF)
        analysis = analyze_brief("brief-002", fields)
        assert len(analysis.gaps) >= 3
        gap_text = " ".join(analysis.gaps).lower()
        assert "audience" in gap_text
        assert "category" in gap_text
        assert "geographic" in gap_text

    def test_gaps_use_human_readable_labels(self):
        fields = _fields(INCOMPLETE_BRIEF)
        analysis = analyze_brief("brief-002", fields)
        for gap in analysis.gaps:
            # Should use "Target Audience" not "audience"
            assert gap[0].isupper()


# ---------------------------------------------------------------------------
# AC-2: User can accept/reject each assumption
# ---------------------------------------------------------------------------

class TestAssumptionResolution:
    def test_incomplete_brief_generates_assumptions(self):
        fields = _fields(INCOMPLETE_BRIEF)
        analysis = analyze_brief("brief-002", fields)
        assert len(analysis.assumptions) >= 3
        assert all(a.status == AssumptionStatus.PENDING for a in analysis.assumptions)

    def test_complete_brief_generates_no_assumptions(self):
        fields = _fields(COMPLETE_BRIEF)
        analysis = analyze_brief("brief-001", fields)
        assert len(analysis.assumptions) == 0

    def test_accept_assumption(self):
        fields = _fields(INCOMPLETE_BRIEF)
        analysis = analyze_brief("brief-002", fields)
        a = analysis.assumptions[0]
        result = resolve_assumption(analysis, a.assumption_id, AssumptionStatus.ACCEPTED)
        assert result.status == AssumptionStatus.ACCEPTED

    def test_reject_assumption(self):
        fields = _fields(INCOMPLETE_BRIEF)
        analysis = analyze_brief("brief-002", fields)
        a = analysis.assumptions[0]
        result = resolve_assumption(analysis, a.assumption_id, AssumptionStatus.REJECTED)
        assert result.status == AssumptionStatus.REJECTED

    def test_cannot_set_back_to_pending(self):
        fields = _fields(INCOMPLETE_BRIEF)
        analysis = analyze_brief("brief-002", fields)
        a = analysis.assumptions[0]
        with pytest.raises(ValueError, match="pending"):
            resolve_assumption(analysis, a.assumption_id, AssumptionStatus.PENDING)

    def test_unknown_assumption_raises(self):
        fields = _fields(INCOMPLETE_BRIEF)
        analysis = analyze_brief("brief-002", fields)
        with pytest.raises(ValueError, match="not found"):
            resolve_assumption(analysis, "nonexistent", AssumptionStatus.ACCEPTED)

    def test_all_resolved_after_decisions(self):
        fields = _fields(INCOMPLETE_BRIEF)
        analysis = analyze_brief("brief-002", fields)
        for a in analysis.assumptions:
            resolve_assumption(analysis, a.assumption_id, AssumptionStatus.ACCEPTED)
        assert analysis.all_resolved()

    def test_not_resolved_with_pending(self):
        fields = _fields(INCOMPLETE_BRIEF)
        analysis = analyze_brief("brief-002", fields)
        assert not analysis.all_resolved()

    def test_each_assumption_has_required_fields(self):
        fields = _fields(INCOMPLETE_BRIEF)
        analysis = analyze_brief("brief-002", fields)
        for a in analysis.assumptions:
            assert a.assumption_id
            assert a.field
            assert a.proposal
            assert a.rationale
            assert a.source_reference


# ---------------------------------------------------------------------------
# AC-3: Accepted assumptions become part of generation context
# ---------------------------------------------------------------------------

class TestAssumptionApplication:
    def test_apply_fills_missing_fields(self):
        fields = _fields(INCOMPLETE_BRIEF)
        analysis = analyze_brief("brief-002", fields)
        for a in analysis.assumptions:
            resolve_assumption(analysis, a.assumption_id, AssumptionStatus.ACCEPTED)
        apply_accepted_assumptions(fields, analysis)
        # All assumed fields should now be populated
        for a in analysis.accepted_assumptions():
            assert getattr(fields, a.field) == a.proposal

    def test_rejected_assumptions_not_applied(self):
        fields = _fields(INCOMPLETE_BRIEF)
        analysis = analyze_brief("brief-002", fields)
        audience_assumption = next(a for a in analysis.assumptions if a.field == "audience")
        resolve_assumption(analysis, audience_assumption.assumption_id, AssumptionStatus.REJECTED)
        for a in analysis.assumptions:
            if a.status == AssumptionStatus.PENDING:
                resolve_assumption(analysis, a.assumption_id, AssumptionStatus.ACCEPTED)
        apply_accepted_assumptions(fields, analysis)
        assert fields.audience is None  # rejected, not applied

    def test_apply_does_not_overwrite_existing_values(self):
        fields = _fields(INCOMPLETE_BRIEF)
        original_objectives = fields.objectives
        analysis = analyze_brief("brief-002", fields)
        for a in analysis.assumptions:
            resolve_assumption(analysis, a.assumption_id, AssumptionStatus.ACCEPTED)
        apply_accepted_assumptions(fields, analysis)
        assert fields.objectives == original_objectives  # was not missing, not overwritten

    def test_fields_become_complete_after_apply(self):
        fields = _fields(INCOMPLETE_BRIEF)
        analysis = analyze_brief("brief-002", fields)
        for a in analysis.assumptions:
            resolve_assumption(analysis, a.assumption_id, AssumptionStatus.ACCEPTED)
        apply_accepted_assumptions(fields, analysis)
        assert fields.is_complete()

    def test_to_brief_context_after_apply(self):
        fields = _fields(INCOMPLETE_BRIEF)
        analysis = analyze_brief("brief-002", fields)
        for a in analysis.assumptions:
            resolve_assumption(analysis, a.assumption_id, AssumptionStatus.ACCEPTED)
        apply_accepted_assumptions(fields, analysis)
        ctx = fields.to_brief_context("brief-002")
        assert ctx.audience is not None
        assert ctx.category is not None
        assert ctx.geography is not None


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------

class TestAnalyzerAPI:
    def _upload_incomplete_brief(self) -> str:
        resp = client.post(
            "/api/v1/briefs/upload?project_id=proj-001",
            files={"file": ("incomplete.md", INCOMPLETE_BRIEF.encode("utf-8"), "text/markdown")},
        )
        assert resp.status_code == 200
        return resp.json()["brief_id"]

    def test_analyze_endpoint(self):
        brief_id = self._upload_incomplete_brief()
        resp = client.post(f"/api/v1/briefs/{brief_id}/analyze")
        assert resp.status_code == 200
        body = resp.json()
        assert body["brief_id"] == brief_id
        assert len(body["summary"]) > 0
        assert len(body["gaps"]) >= 3
        assert len(body["assumptions"]) >= 3
        assert body["all_resolved"] is False

    def test_analyze_complete_brief_no_assumptions(self):
        resp = client.post(
            "/api/v1/briefs/upload?project_id=proj-001",
            files={"file": ("complete.md", COMPLETE_BRIEF.encode("utf-8"), "text/markdown")},
        )
        brief_id = resp.json()["brief_id"]
        resp = client.post(f"/api/v1/briefs/{brief_id}/analyze")
        assert resp.status_code == 200
        assert len(resp.json()["assumptions"]) == 0
        assert resp.json()["all_resolved"] is True

    def test_resolve_assumption_endpoint(self):
        brief_id = self._upload_incomplete_brief()
        analysis = client.post(f"/api/v1/briefs/{brief_id}/analyze").json()
        analysis_id = analysis["analysis_id"]
        assumption_id = analysis["assumptions"][0]["assumption_id"]

        resp = client.patch(
            f"/api/v1/briefs/analysis/{analysis_id}/assumptions/{assumption_id}",
            json={"decision": "accepted"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    def test_reject_assumption_endpoint(self):
        brief_id = self._upload_incomplete_brief()
        analysis = client.post(f"/api/v1/briefs/{brief_id}/analyze").json()
        analysis_id = analysis["analysis_id"]
        assumption_id = analysis["assumptions"][0]["assumption_id"]

        resp = client.patch(
            f"/api/v1/briefs/analysis/{analysis_id}/assumptions/{assumption_id}",
            json={"decision": "rejected"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_apply_assumptions_endpoint(self):
        brief_id = self._upload_incomplete_brief()
        analysis = client.post(f"/api/v1/briefs/{brief_id}/analyze").json()
        analysis_id = analysis["analysis_id"]

        # Accept all
        for a in analysis["assumptions"]:
            client.patch(
                f"/api/v1/briefs/analysis/{analysis_id}/assumptions/{a['assumption_id']}",
                json={"decision": "accepted"},
            )

        resp = client.post(f"/api/v1/briefs/analysis/{analysis_id}/apply")
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_complete"] is True
        assert body["accepted_count"] >= 3

    def test_apply_with_pending_returns_400(self):
        brief_id = self._upload_incomplete_brief()
        analysis = client.post(f"/api/v1/briefs/{brief_id}/analyze").json()
        analysis_id = analysis["analysis_id"]
        # Don't resolve any assumptions
        resp = client.post(f"/api/v1/briefs/analysis/{analysis_id}/apply")
        assert resp.status_code == 400
        assert "pending" in resp.json()["detail"]

    def test_analyze_nonexistent_brief_returns_404(self):
        resp = client.post("/api/v1/briefs/nonexistent/analyze")
        assert resp.status_code == 404
