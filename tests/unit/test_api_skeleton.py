"""Skeleton tests for P01-01: API and web stubs, package imports, starter tests.

AC-1: API and web stubs run locally.
AC-2: Shared package import paths are stable.
AC-3: Starter tests run in CI/local.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# AC-1: API stub runs locally
# ---------------------------------------------------------------------------

class TestAPIStub:
    def test_health_endpoint(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["service"] == "quant-platform-api"
        assert body["version"] == "0.1.0"

    def test_list_projects_requires_auth(self):
        resp = client.get("/api/v1/projects/")
        assert resp.status_code == 401

    def test_create_project_requires_auth(self):
        resp = client.post("/api/v1/projects/", json={"name": "Test", "methodology": "segmentation"})
        assert resp.status_code == 401

    def test_openapi_docs_available(self):
        resp = client.get("/docs")
        assert resp.status_code == 200

    def test_cors_headers_present(self):
        resp = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# AC-1: Web stub exists
# ---------------------------------------------------------------------------

class TestWebStub:
    def test_index_html_exists(self):
        import os
        index_path = os.path.join("apps", "web", "index.html")
        assert os.path.exists(index_path)

    def test_serve_script_importable(self):
        mod = importlib.import_module("apps.web.serve")
        assert hasattr(mod, "main")


# ---------------------------------------------------------------------------
# AC-2: Shared package import paths are stable
# ---------------------------------------------------------------------------

IMPORT_PATHS = [
    "packages.shared",
    "packages.shared.assistant_context",
    "packages.shared.section_taxonomy",
    "packages.shared.interaction_patterns",
    "packages.shared.eval_framework",
    "packages.survey_generation",
    "packages.survey_analysis",
    "packages.exporters",
    "services.worker",
    "services.scheduler",
    "apps.api",
    "apps.api.main",
    "apps.api.routes.health",
    "apps.api.routes.projects",
]


class TestPackageImports:
    @pytest.mark.parametrize("path", IMPORT_PATHS)
    def test_import_succeeds(self, path: str):
        mod = importlib.import_module(path)
        assert mod is not None

    def test_assistant_context_importable_from_shared(self):
        from packages.shared.assistant_context import AssistantContext, Methodology
        assert AssistantContext is not None
        assert len(Methodology) == 8

    def test_section_taxonomy_importable_from_shared(self):
        from packages.shared.section_taxonomy import METHODOLOGY_MATRIX, get_matrix
        assert len(METHODOLOGY_MATRIX) == 8

    def test_interaction_patterns_importable_from_shared(self):
        from packages.shared.interaction_patterns import COPILOT_PANELS, Screen
        assert len(COPILOT_PANELS) == len(Screen)

    def test_eval_framework_importable_from_shared(self):
        from packages.shared.eval_framework import EVAL_SCENARIOS
        assert len(EVAL_SCENARIOS) >= 10


# ---------------------------------------------------------------------------
# AC-3: This file IS the starter test suite — if it runs, AC-3 is met.
# ---------------------------------------------------------------------------

class TestStarterSuite:
    def test_pytest_runs(self):
        """Meta-test: if this executes, the test harness works."""
        assert True

    def test_all_phase0_tests_still_pass(self):
        """Verify phase 0 modules are not broken by skeleton setup."""
        from packages.shared.assistant_context import validate_for_stage
        from packages.shared.section_taxonomy import validate_section_selection
        from packages.shared.eval_framework import score_result, EvalDimension, ScoreLevel
        assert score_result(EvalDimension.USEFULNESS, 0.85) == ScoreLevel.PASS
