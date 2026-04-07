"""Observability: structured logging, metrics collection, and SLO tracking.

Provides:
- Request context with correlation IDs (request_id, project_id, user_id)
- Metrics collector for latency, error rates, queue depth, job success rate
- SLO definitions and threshold checks
- FastAPI middleware for automatic request instrumentation

AC-1: Structured logs include request_id, project_id, user_id, run_id
AC-2: Metrics track latency, job success rate, queue depth, error rate
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request context (thread-local correlation IDs)
# ---------------------------------------------------------------------------

_context = threading.local()


@dataclass
class RequestContext:
    """Correlation IDs for a single request."""
    request_id: str = ""
    project_id: str = ""
    user_id: str = ""
    run_id: str = ""
    method: str = ""
    path: str = ""


def get_request_context() -> RequestContext:
    """Return the current request context (or empty if none set)."""
    return getattr(_context, "current", RequestContext())


def set_request_context(ctx: RequestContext) -> None:
    _context.current = ctx


def clear_request_context() -> None:
    _context.current = RequestContext()


@contextmanager
def request_scope(
    request_id: str | None = None,
    project_id: str = "",
    user_id: str = "",
    run_id: str = "",
    method: str = "",
    path: str = "",
):
    """Context manager that sets and clears request context."""
    ctx = RequestContext(
        request_id=request_id or uuid.uuid4().hex[:16],
        project_id=project_id,
        user_id=user_id,
        run_id=run_id,
        method=method,
        path=path,
    )
    set_request_context(ctx)
    try:
        yield ctx
    finally:
        clear_request_context()


def structured_log(
    level: int,
    message: str,
    *,
    extra: dict[str, Any] | None = None,
    **kwargs: Any,
) -> None:
    """Emit a structured log entry with correlation IDs from request context."""
    ctx = get_request_context()
    log_data = {
        "request_id": ctx.request_id,
        "project_id": ctx.project_id,
        "user_id": ctx.user_id,
        "run_id": ctx.run_id,
        "method": ctx.method,
        "path": ctx.path,
    }
    if extra:
        log_data.update(extra)
    log_data.update(kwargs)

    # Filter out unset context fields (empty strings) but keep real values like 0, False
    log_data = {k: v for k, v in log_data.items() if v is not None and v != ""}

    logger.log(level, "%s | %s", message, log_data)


# ---------------------------------------------------------------------------
# Metrics collector
# ---------------------------------------------------------------------------

class MetricsCollector:
    """Thread-safe in-memory metrics collector.

    Tracks counters, histograms (for latency), and gauges.
    Designed for lightweight observability without external dependencies.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._gauges: dict[str, float] = {}

    def increment(self, name: str, value: int = 1, labels: dict[str, str] | None = None) -> None:
        """Increment a counter."""
        key = self._key(name, labels)
        with self._lock:
            self._counters[key] += value

    def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Record an observation in a histogram (e.g., latency)."""
        key = self._key(name, labels)
        with self._lock:
            self._histograms[key].append(value)

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Set a gauge to a specific value."""
        key = self._key(name, labels)
        with self._lock:
            self._gauges[key] = value

    def increment_gauge(self, name: str, delta: float, labels: dict[str, str] | None = None) -> None:
        """Atomically increment a gauge by delta."""
        key = self._key(name, labels)
        with self._lock:
            self._gauges[key] = self._gauges.get(key, 0.0) + delta

    def get_counter(self, name: str, labels: dict[str, str] | None = None) -> int:
        key = self._key(name, labels)
        with self._lock:
            return self._counters.get(key, 0)

    def get_histogram(self, name: str, labels: dict[str, str] | None = None) -> list[float]:
        key = self._key(name, labels)
        with self._lock:
            return list(self._histograms.get(key, []))

    def get_gauge(self, name: str, labels: dict[str, str] | None = None) -> float:
        key = self._key(name, labels)
        with self._lock:
            return self._gauges.get(key, 0.0)

    def get_percentile(self, name: str, p: float, labels: dict[str, str] | None = None) -> float:
        """Get a percentile from a histogram. p in [0, 100].

        Uses linear interpolation (same as numpy's default method).
        """
        values = self.get_histogram(name, labels)
        if not values:
            return 0.0
        return self._percentile(values, p)

    def snapshot(self) -> dict[str, Any]:
        """Return a snapshot of all metrics."""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    k: {
                        "count": len(v),
                        "min": min(v) if v else 0,
                        "max": max(v) if v else 0,
                        "p50": self._percentile(v, 50),
                        "p95": self._percentile(v, 95),
                        "p99": self._percentile(v, 99),
                    }
                    for k, v in self._histograms.items()
                },
            }

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._counters.clear()
            self._histograms.clear()
            self._gauges.clear()

    @staticmethod
    def _key(name: str, labels: dict[str, str] | None) -> str:
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    @staticmethod
    def _percentile(values: list[float], p: float) -> float:
        """Linear interpolation percentile (matches numpy default)."""
        if not values:
            return 0.0
        s = sorted(values)
        n = len(s)
        if n == 1:
            return s[0]
        # Linear interpolation between nearest ranks
        rank = (p / 100) * (n - 1)
        lo = int(rank)
        hi = min(lo + 1, n - 1)
        frac = rank - lo
        return s[lo] + frac * (s[hi] - s[lo])


# Global metrics instance
metrics = MetricsCollector()


# ---------------------------------------------------------------------------
# SLO definitions and checks
# ---------------------------------------------------------------------------

@dataclass
class SLODefinition:
    """Service Level Objective definition."""
    name: str
    metric_name: str
    threshold: float
    comparison: str  # "lt" (less than), "gt" (greater than), "lte", "gte"
    description: str = ""


# Default SLOs for the platform
DEFAULT_SLOS: list[SLODefinition] = [
    # API reliability
    SLODefinition(
        name="api_latency_p95",
        metric_name="http_request_duration_ms",
        threshold=500.0,
        comparison="lte",
        description="95th percentile API latency <= 500ms",
    ),
    SLODefinition(
        name="api_error_rate",
        metric_name="http_request_errors",
        threshold=0.05,
        comparison="lte",
        description="Error rate <= 5%",
    ),
    SLODefinition(
        name="api_availability",
        metric_name="api_availability",
        threshold=0.99,
        comparison="gte",
        description="API availability >= 99% (successful requests / total)",
    ),
    # Job health
    SLODefinition(
        name="job_success_rate",
        metric_name="job_success_rate",
        threshold=0.95,
        comparison="gte",
        description="Job success rate >= 95%",
    ),
    SLODefinition(
        name="job_queue_depth",
        metric_name="job_queue_depth",
        threshold=100.0,
        comparison="lte",
        description="Queue depth <= 100 pending jobs",
    ),
    SLODefinition(
        name="analysis_completion_time_p95",
        metric_name="analysis_duration_ms",
        threshold=30000.0,
        comparison="lte",
        description="95th percentile analysis run completion <= 30s",
    ),
    # Cost
    SLODefinition(
        name="cost_per_run_usd",
        metric_name="cost_per_run_usd",
        threshold=0.50,
        comparison="lte",
        description="Average cost per analysis run <= $0.50",
    ),
]


def check_slo(slo: SLODefinition, value: float) -> dict[str, Any]:
    """Check a single SLO against a measured value."""
    ops = {
        "lt": lambda v, t: v < t,
        "gt": lambda v, t: v > t,
        "lte": lambda v, t: v <= t,
        "gte": lambda v, t: v >= t,
    }
    op = ops.get(slo.comparison)
    if not op:
        raise ValueError(f"Unknown comparison: {slo.comparison!r}")

    passing = op(value, slo.threshold)
    return {
        "name": slo.name,
        "description": slo.description,
        "threshold": slo.threshold,
        "actual": value,
        "passing": passing,
    }


def check_all_slos(collector: MetricsCollector | None = None) -> list[dict[str, Any]]:
    """Check all default SLOs against current metrics."""
    m = collector or metrics
    slo_map = {s.name: s for s in DEFAULT_SLOS}
    results = []

    # API latency p95
    p95 = m.get_percentile("http_request_duration_ms", 95)
    results.append(check_slo(slo_map["api_latency_p95"], p95))

    # Error rate
    total_requests = m.get_counter("http_requests_total")
    error_count = m.get_counter("http_request_errors")
    error_rate = error_count / total_requests if total_requests > 0 else 0.0
    results.append(check_slo(slo_map["api_error_rate"], error_rate))

    # API availability (successful / total)
    availability = (total_requests - error_count) / total_requests if total_requests > 0 else 1.0
    results.append(check_slo(slo_map["api_availability"], availability))

    # Job success rate
    jobs_completed = m.get_counter("jobs_completed")
    jobs_failed = m.get_counter("jobs_failed")
    total_jobs = jobs_completed + jobs_failed
    success_rate = jobs_completed / total_jobs if total_jobs > 0 else 1.0
    results.append(check_slo(slo_map["job_success_rate"], success_rate))

    # Queue depth
    queue_depth = m.get_gauge("job_queue_depth")
    results.append(check_slo(slo_map["job_queue_depth"], queue_depth))

    # Analysis completion time p95
    analysis_p95 = m.get_percentile("analysis_duration_ms", 95)
    results.append(check_slo(slo_map["analysis_completion_time_p95"], analysis_p95))

    # Cost per run
    total_cost = m.get_gauge("llm_cost_total_usd")
    total_runs = jobs_completed + jobs_failed
    cost_per_run = total_cost / total_runs if total_runs > 0 else 0.0
    results.append(check_slo(slo_map["cost_per_run_usd"], cost_per_run))

    return results


# ---------------------------------------------------------------------------
# Instrumentation helpers
# ---------------------------------------------------------------------------

@contextmanager
def track_latency(metric_name: str, labels: dict[str, str] | None = None):
    """Context manager to measure and record execution time."""
    start = time.monotonic()
    try:
        yield
    finally:
        duration_ms = (time.monotonic() - start) * 1000
        metrics.observe(metric_name, duration_ms, labels)


def record_request(method: str, path: str, status_code: int, duration_ms: float) -> None:
    """Record an HTTP request in metrics.

    Increments both labeled (per-endpoint) and unlabeled (aggregate) counters
    so SLO checks can read the aggregate without scanning all label combinations.
    """
    labels = {"method": method, "path": path}
    metrics.increment("http_requests_total")
    metrics.increment("http_requests_total", labels=labels)
    metrics.observe("http_request_duration_ms", duration_ms)
    metrics.observe("http_request_duration_ms", duration_ms, labels=labels)
    if status_code >= 500:
        metrics.increment("http_request_errors")
        metrics.increment("http_request_errors", labels=labels)


def record_job_result(job_type: str, success: bool) -> None:
    """Record a job completion/failure in metrics."""
    if success:
        metrics.increment("jobs_completed")
        metrics.increment("jobs_completed", labels={"type": job_type})
    else:
        metrics.increment("jobs_failed")
        metrics.increment("jobs_failed", labels={"type": job_type})


def record_stuck_jobs(stuck_count: int, oldest_age_seconds: float = 0.0) -> None:
    """Update stuck-job gauges. Called periodically by the worker monitor.

    stuck_count: number of jobs in RUNNING state beyond expected duration.
    oldest_age_seconds: age of the oldest stuck job in seconds.
    """
    metrics.set_gauge("jobs_stuck", float(stuck_count))
    metrics.set_gauge("oldest_running_job_age_s", oldest_age_seconds)
