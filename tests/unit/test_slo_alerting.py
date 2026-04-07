"""Tests for P11-02: SLOs and alerting for reliability and spend anomalies.

AC-1: SLOs documented for API availability, latency, and analysis run completion.
AC-2: Alerts route to owners for threshold breaches and sustained degradations.
AC-3: Cost anomaly alerts for sudden increases in token/compute spend.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.routes.dashboard import get_alert_engine, record_llm_cost
from packages.shared.alerting import (
    Alert,
    AlertEngine,
    AlertSeverity,
    AlertState,
    CostAnomalyDetector,
    LogAlertHandler,
    get_owner,
    ALERT_OWNERS,
)
from packages.shared.observability import (
    DEFAULT_SLOS,
    MetricsCollector,
    check_all_slos,
    metrics,
    record_job_result,
    record_request,
    record_stuck_jobs,
)


@pytest.fixture(autouse=True)
def reset():
    metrics.reset()
    # Reset the singleton alert engine state
    engine = get_alert_engine()
    engine._active_alerts.clear()
    engine._history.clear()
    engine.cost_detector._readings.clear()
    engine.cost_detector._above_count = 0
    yield
    metrics.reset()


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# AC-1: SLOs for availability, latency, analysis completion
# ---------------------------------------------------------------------------

class TestSLODefinitions:
    def test_api_availability_slo_exists(self):
        names = {s.name for s in DEFAULT_SLOS}
        assert "api_availability" in names

    def test_api_latency_slo_exists(self):
        names = {s.name for s in DEFAULT_SLOS}
        assert "api_latency_p95" in names

    def test_analysis_completion_slo_exists(self):
        names = {s.name for s in DEFAULT_SLOS}
        assert "analysis_completion_time_p95" in names

    def test_cost_per_run_slo_exists(self):
        names = {s.name for s in DEFAULT_SLOS}
        assert "cost_per_run_usd" in names

    def test_slo_count_is_seven(self):
        assert len(DEFAULT_SLOS) == 7

    def test_check_all_slos_returns_seven(self):
        results = check_all_slos()
        assert len(results) == 7

    def test_availability_passes_with_healthy_traffic(self):
        for _ in range(100):
            record_request("GET", "/api", 200, 10.0)
        record_request("GET", "/api", 500, 10.0)  # 1 error in 101
        results = check_all_slos()
        avail = [r for r in results if r["name"] == "api_availability"][0]
        assert avail["passing"] is True  # 100/101 = 99%+

    def test_availability_fails_with_many_errors(self):
        for _ in range(90):
            record_request("GET", "/api", 200, 10.0)
        for _ in range(10):
            record_request("GET", "/api", 500, 10.0)
        results = check_all_slos()
        avail = [r for r in results if r["name"] == "api_availability"][0]
        # 90/100 = 0.90 < 0.99 threshold → FAIL
        assert avail["passing"] is False

    def test_analysis_completion_slo_passes_with_fast_runs(self):
        for _ in range(10):
            metrics.observe("analysis_duration_ms", 5000.0)  # 5s each
        results = check_all_slos()
        comp = [r for r in results if r["name"] == "analysis_completion_time_p95"][0]
        assert comp["passing"] is True  # 5s < 30s

    def test_analysis_completion_slo_fails_with_slow_runs(self):
        for _ in range(10):
            metrics.observe("analysis_duration_ms", 60000.0)  # 60s each
        results = check_all_slos()
        comp = [r for r in results if r["name"] == "analysis_completion_time_p95"][0]
        assert comp["passing"] is False  # 60s > 30s


# ---------------------------------------------------------------------------
# AC-2: Alert routing to owners
# ---------------------------------------------------------------------------

class TestAlertRouting:
    def test_all_slos_have_owners(self):
        for slo in DEFAULT_SLOS:
            owner = get_owner(slo.name)
            assert owner, f"No owner for SLO: {slo.name}"

    def test_cost_alerts_have_owners(self):
        assert get_owner("cost_spike") != ""
        assert get_owner("cost_sustained_increase") != ""

    def test_unknown_alert_defaults_to_platform_team(self):
        assert get_owner("unknown_alert") == "Platform Team"

    def test_alert_includes_owner(self):
        engine = AlertEngine()
        # Force an SLO breach
        for _ in range(10):
            record_request("GET", "/api", 500, 10.0)
        alerts = engine.evaluate()
        firing = [a for a in alerts if a.state == AlertState.FIRING]
        assert len(firing) > 0
        for alert in firing:
            assert alert.owner != ""

    def test_alert_fires_on_slo_breach(self):
        engine = AlertEngine()
        # Trigger error rate breach: 100% errors
        for _ in range(10):
            record_request("GET", "/api", 500, 100.0)
        alerts = engine.evaluate()
        firing = [a for a in alerts if a.state == AlertState.FIRING]
        assert any(a.name == "api_error_rate" for a in firing)

    def test_alert_resolves_when_slo_recovers(self):
        engine = AlertEngine()
        # Fire
        for _ in range(10):
            record_request("GET", "/api", 500, 100.0)
        engine.evaluate()
        assert len(engine.active_alerts) > 0

        # Recover: flood with successful requests
        for _ in range(1000):
            record_request("GET", "/api", 200, 10.0)
        alerts = engine.evaluate()
        resolved = [a for a in alerts if a.state == AlertState.RESOLVED]
        assert len(resolved) > 0

    def test_alert_not_duplicated_while_firing(self):
        engine = AlertEngine()
        for _ in range(10):
            record_request("GET", "/api", 500, 100.0)
        alerts1 = engine.evaluate()
        alerts2 = engine.evaluate()
        # Second evaluation should not fire the same alert again
        firing2 = [a for a in alerts2 if a.state == AlertState.FIRING and a.name == "api_error_rate"]
        assert len(firing2) == 0

    def test_log_handler_does_not_raise(self):
        handler = LogAlertHandler()
        alert = Alert(
            alert_id="test", name="test", severity=AlertSeverity.WARNING,
            state=AlertState.FIRING, message="Test alert",
        )
        handler.handle(alert)  # should not raise
        alert.state = AlertState.RESOLVED
        handler.handle(alert)  # should not raise


# ---------------------------------------------------------------------------
# AC-3: Cost anomaly detection
# ---------------------------------------------------------------------------

class TestCostAnomalyDetection:
    def test_no_alert_on_first_reading(self):
        detector = CostAnomalyDetector()
        alerts = detector.add_reading(0.01)
        assert len(alerts) == 0

    def test_no_alert_on_steady_cost(self):
        detector = CostAnomalyDetector()
        for _ in range(5):
            alerts = detector.add_reading(0.01)
        assert len(alerts) == 0

    def test_spike_detected(self):
        detector = CostAnomalyDetector(spike_threshold_pct=100.0)
        for _ in range(5):
            detector.add_reading(0.01)
        # Sudden 10x spike
        alerts = detector.add_reading(0.10)
        spike_alerts = [a for a in alerts if a.name == "cost_spike"]
        assert len(spike_alerts) == 1
        assert spike_alerts[0].severity == AlertSeverity.WARNING

    def test_sustained_increase_detected(self):
        detector = CostAnomalyDetector(
            sustained_threshold_pct=50.0,
            sustained_count=3,
        )
        # Baseline
        for _ in range(5):
            detector.add_reading(0.01)
        # Sustained 2x increase
        all_alerts = []
        for _ in range(4):
            alerts = detector.add_reading(0.02)
            all_alerts.extend(alerts)
        sustained = [a for a in all_alerts if a.name == "cost_sustained_increase"]
        assert len(sustained) >= 1
        assert sustained[0].severity == AlertSeverity.CRITICAL

    def test_no_sustained_alert_if_cost_returns_to_normal(self):
        detector = CostAnomalyDetector(sustained_threshold_pct=50.0, sustained_count=3)
        for _ in range(5):
            detector.add_reading(0.01)
        detector.add_reading(0.02)  # above
        detector.add_reading(0.01)  # back to normal — resets count
        detector.add_reading(0.02)  # above again
        alerts = detector.add_reading(0.02)
        sustained = [a for a in alerts if a.name == "cost_sustained_increase"]
        assert len(sustained) == 0  # not enough consecutive readings


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

class TestAlertEndpoints:
    def test_alerts_endpoint(self, client):
        resp = client.get("/ops/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_count" in data
        assert "active_alerts" in data

    def test_evaluate_endpoint(self, client):
        resp = client.post("/ops/alerts/evaluate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["evaluated"] is True
        assert "new_alerts" in data
        assert "active_count" in data

    def test_evaluate_with_breach(self, client):
        for _ in range(10):
            record_request("GET", "/api", 500, 100.0)
        resp = client.post("/ops/alerts/evaluate")
        data = resp.json()
        assert data["new_alerts"] > 0

    def test_slos_endpoint_returns_seven(self, client):
        resp = client.get("/ops/slos")
        assert resp.status_code == 200
        assert len(resp.json()["slos"]) == 7
