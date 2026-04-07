"""Health and operations dashboard endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from packages.shared.observability import check_all_slos, metrics
from apps.api.routes.dashboard import _extract_labeled

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, object]:
    """Basic health check for load balancers and uptime monitors.

    Kept lightweight — no SLO computation. Use /health/detailed for full status.
    """
    return {
        "ok": True,
        "service": "quant-platform-api",
        "version": "0.1.0",
    }


@router.get("/health/detailed")
def health_detailed() -> dict[str, Any]:
    """Detailed health with SLO status, job health, and dependency checks."""
    slo_results = check_all_slos()
    snapshot = metrics.snapshot()

    return {
        "ok": True,
        "service": "quant-platform-api",
        "version": "0.1.0",
        "slos": slo_results,
        "api_health": {
            "total_requests": metrics.get_counter("http_requests_total"),
            "error_count": metrics.get_counter("http_request_errors"),
            "latency_p50_ms": metrics.get_percentile("http_request_duration_ms", 50),
            "latency_p95_ms": metrics.get_percentile("http_request_duration_ms", 95),
            "latency_p99_ms": metrics.get_percentile("http_request_duration_ms", 99),
        },
        "job_health": {
            "completed": metrics.get_counter("jobs_completed"),
            "failed": metrics.get_counter("jobs_failed"),
            "queue_depth": metrics.get_gauge("job_queue_depth"),
            "stuck_count": int(metrics.get_gauge("jobs_stuck")),
            "oldest_running_age_s": metrics.get_gauge("oldest_running_job_age_s"),
        },
        "cost": {
            "total_tokens": metrics.get_counter("llm_tokens_total"),
            "total_cost_usd": metrics.get_gauge("llm_cost_total_usd"),
            "cost_by_stage": _extract_labeled("llm_cost_usd", snapshot.get("gauges", {})),
        },
    }
