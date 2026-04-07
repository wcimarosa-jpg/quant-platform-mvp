"""Tests for P11-01: Operations dashboard for API health, job health, and cost.

AC-1: Dashboard includes API uptime, error rate, latency percentiles, dependency health.
AC-2: Dashboard includes queue depth, job success/failure rates, stuck job indicators.
AC-3: Dashboard includes token usage and cost by workflow stage, project, timeframe.
AC-4: Dashboard includes total portfolio cost and rolling averages.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.routes.dashboard import record_llm_cost
from packages.shared.observability import metrics, record_job_result, record_request, record_stuck_jobs


@pytest.fixture(autouse=True)
def reset():
    metrics.reset()
    yield
    metrics.reset()


@pytest.fixture
def client():
    return TestClient(app)


def _seed_metrics():
    """Seed realistic metrics for dashboard tests."""
    for _ in range(50):
        record_request("GET", "/api/v1/health", 200, 15.0)
    for _ in range(5):
        record_request("POST", "/api/v1/tables/generate", 200, 250.0)
    record_request("POST", "/api/v1/run", 500, 100.0)
    record_job_result("drivers", True)
    record_job_result("drivers", True)
    record_job_result("segmentation", True)
    record_job_result("maxdiff_turf", False)
    metrics.set_gauge("job_queue_depth", 3.0)
    record_llm_cost(1500, 0.0045, stage="brief_analysis", project_id="proj-1", run_id="run-1")
    record_llm_cost(3000, 0.009, stage="questionnaire_gen", project_id="proj-1", run_id="run-2")
    record_llm_cost(500, 0.0015, stage="insight_narrative", project_id="proj-2")


# ---------------------------------------------------------------------------
# AC-1: API Health
# ---------------------------------------------------------------------------

class TestAPIHealth:
    def test_health_basic(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["version"] == "0.1.0"

    def test_health_detailed(self, client):
        _seed_metrics()
        resp = client.get("/health/detailed")
        assert resp.status_code == 200
        data = resp.json()
        assert "api_health" in data
        assert "job_health" in data
        assert "slos" in data
        assert "cost" in data

    def test_api_health_has_latency_percentiles(self, client):
        _seed_metrics()
        data = client.get("/health/detailed").json()
        api = data["api_health"]
        assert "latency_p50_ms" in api
        assert "latency_p95_ms" in api
        assert "latency_p99_ms" in api
        assert api["latency_p50_ms"] >= 0

    def test_api_health_has_error_count(self, client):
        _seed_metrics()
        data = client.get("/health/detailed").json()
        assert data["api_health"]["error_count"] >= 1

    def test_api_health_has_total_requests(self, client):
        _seed_metrics()
        data = client.get("/health/detailed").json()
        assert data["api_health"]["total_requests"] > 0


# ---------------------------------------------------------------------------
# AC-2: Job Health
# ---------------------------------------------------------------------------

class TestJobHealth:
    def test_job_health_in_detailed(self, client):
        _seed_metrics()
        data = client.get("/health/detailed").json()
        job = data["job_health"]
        assert "completed" in job
        assert "failed" in job
        assert "queue_depth" in job

    def test_job_completed_count(self, client):
        _seed_metrics()
        data = client.get("/health/detailed").json()
        assert data["job_health"]["completed"] == 3

    def test_job_failed_count(self, client):
        _seed_metrics()
        data = client.get("/health/detailed").json()
        assert data["job_health"]["failed"] == 1

    def test_queue_depth(self, client):
        _seed_metrics()
        data = client.get("/health/detailed").json()
        assert data["job_health"]["queue_depth"] == 3.0

    def test_stuck_count_default_zero(self, client):
        data = client.get("/health/detailed").json()
        assert data["job_health"]["stuck_count"] == 0

    def test_stuck_count_recorded(self, client):
        record_stuck_jobs(2, oldest_age_seconds=120.5)
        data = client.get("/health/detailed").json()
        assert data["job_health"]["stuck_count"] == 2
        assert data["job_health"]["oldest_running_age_s"] == 120.5


# ---------------------------------------------------------------------------
# AC-3: Cost tracking
# ---------------------------------------------------------------------------

class TestCostTracking:
    def test_cost_endpoint(self, client):
        _seed_metrics()
        resp = client.get("/ops/cost")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_tokens" in data
        assert "total_cost_usd" in data

    def test_total_tokens(self, client):
        _seed_metrics()
        data = client.get("/ops/cost").json()
        assert data["total_tokens"] == 5000  # 1500 + 3000 + 500

    def test_total_cost(self, client):
        _seed_metrics()
        data = client.get("/ops/cost").json()
        assert abs(data["total_cost_usd"] - 0.015) < 0.001

    def test_cost_by_stage(self, client):
        _seed_metrics()
        data = client.get("/ops/cost").json()
        stages = data["by_stage"]
        assert len(stages) >= 2  # brief_analysis, questionnaire_gen, insight_narrative

    def test_cost_by_project(self, client):
        _seed_metrics()
        data = client.get("/ops/cost").json()
        projects = data["by_project"]
        assert len(projects) >= 1  # proj-1, proj-2

    def test_record_llm_cost_accumulates(self):
        record_llm_cost(100, 0.001, stage="test")
        record_llm_cost(200, 0.002, stage="test")
        assert metrics.get_counter("llm_tokens_total") == 300
        assert abs(metrics.get_gauge("llm_cost_total_usd") - 0.003) < 0.0001


# ---------------------------------------------------------------------------
# AC-1/2/3: Metrics and SLO endpoints
# ---------------------------------------------------------------------------

class TestMetricsEndpoints:
    def test_metrics_snapshot(self, client):
        _seed_metrics()
        resp = client.get("/ops/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "counters" in data
        assert "gauges" in data
        assert "histograms" in data

    def test_slos_endpoint(self, client):
        _seed_metrics()
        resp = client.get("/ops/slos")
        assert resp.status_code == 200
        data = resp.json()
        assert "all_passing" in data
        assert "slos" in data
        assert len(data["slos"]) == 4

    def test_slos_have_required_fields(self, client):
        resp = client.get("/ops/slos").json()
        for slo in resp["slos"]:
            assert "name" in slo
            assert "passing" in slo
            assert "threshold" in slo
            assert "actual" in slo


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

class TestDashboardHTML:
    def test_dashboard_returns_html(self, client):
        resp = client.get("/ops/dashboard")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_dashboard_contains_key_sections(self, client):
        html = client.get("/ops/dashboard").text
        assert "Operations Dashboard" in html
        assert "API Health" in html
        assert "Job Health" in html
        assert "SLOs" in html
        assert "Cost" in html

    def test_dashboard_auto_refreshes(self, client):
        html = client.get("/ops/dashboard").text
        assert "setInterval" in html
