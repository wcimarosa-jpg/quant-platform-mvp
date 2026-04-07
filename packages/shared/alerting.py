"""Alerting engine for SLO breaches and cost anomalies.

Provides:
- Alert generation from SLO check results
- Cost anomaly detection (spike detection via rolling average comparison)
- Alert routing to component owners
- Alert state management (firing, resolved, suppressed)

Integration:
- Called by a periodic monitor (e.g., background task or cron)
- Alerts are logged and stored in-memory; external delivery (Slack, email)
  is pluggable via AlertHandler protocol.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Protocol

from .observability import MetricsCollector, check_all_slos, metrics

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Alert model
# ---------------------------------------------------------------------------

class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertState(str, Enum):
    FIRING = "firing"
    RESOLVED = "resolved"


@dataclass
class Alert:
    """One alert instance."""
    alert_id: str
    name: str
    severity: AlertSeverity
    state: AlertState
    message: str
    owner: str = ""
    metric_value: float = 0.0
    threshold: float = 0.0
    fired_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    resolved_at: datetime | None = None
    labels: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "name": self.name,
            "severity": self.severity.value,
            "state": self.state.value,
            "message": self.message,
            "owner": self.owner,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "fired_at": self.fired_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "labels": self.labels,
        }


# ---------------------------------------------------------------------------
# Alert handler protocol (pluggable delivery)
# ---------------------------------------------------------------------------

class AlertHandler(Protocol):
    """Protocol for alert delivery (Slack, email, log, etc.)."""
    def handle(self, alert: Alert) -> None: ...


class LogAlertHandler:
    """Default handler — logs alerts to Python logger."""
    def handle(self, alert: Alert) -> None:
        if alert.state == AlertState.FIRING:
            logger.warning(
                "ALERT FIRING: %s [%s] — %s (value=%s, threshold=%s, owner=%s)",
                alert.name, alert.severity.value, alert.message,
                alert.metric_value, alert.threshold, alert.owner,
            )
        else:
            logger.info(
                "ALERT RESOLVED: %s — %s",
                alert.name, alert.message,
            )


# ---------------------------------------------------------------------------
# Owner routing
# ---------------------------------------------------------------------------

# Maps SLO/alert names to component owners (from OWNERSHIP.md)
ALERT_OWNERS: dict[str, str] = {
    "api_latency_p95": "Platform Team",
    "api_error_rate": "Platform Team",
    "api_availability": "Platform Team",
    "job_success_rate": "Platform Team",
    "job_queue_depth": "Platform Team",
    "analysis_completion_time_p95": "Research Team",
    "cost_per_run_usd": "Platform Team",
    "cost_spike": "Platform Team",
    "cost_sustained_increase": "Platform Team",
}


def get_owner(alert_name: str) -> str:
    """Look up the owner for an alert name."""
    return ALERT_OWNERS.get(alert_name, "Platform Team")


# ---------------------------------------------------------------------------
# Cost anomaly detection
# ---------------------------------------------------------------------------

@dataclass
class CostAnomalyDetector:
    """Detects cost spikes and sustained increases.

    Uses a simple rolling window: if the latest cost reading exceeds
    the rolling average by more than `spike_threshold_pct`, fire an alert.
    """
    window_size: int = 10
    spike_threshold_pct: float = 200.0  # fire if 2x the rolling average
    sustained_threshold_pct: float = 50.0  # fire if 50% above average for N readings
    sustained_count: int = 3

    _readings: list[float] = field(default_factory=list)
    _above_count: int = 0
    _spike_firing: bool = False
    _sustained_firing: bool = False
    _reading_counter: int = 0

    def add_reading(self, cost_usd: float) -> list[Alert]:
        """Add a cost reading and return any triggered alerts.

        Uses the previous readings as the baseline (excluding the current one).
        Dedup: only fires each alert type once until the condition clears.
        """
        alerts = []
        self._reading_counter += 1

        if len(self._readings) < 1:
            self._readings.append(cost_usd)
            return alerts

        # Baseline is the previous readings (before appending current)
        baseline = self._readings[-self.window_size:]
        avg = sum(baseline) / len(baseline)
        self._readings.append(cost_usd)
        current = cost_usd

        if avg > 0:
            pct_above = ((current - avg) / avg) * 100

            # Spike detection (deduped)
            if pct_above > self.spike_threshold_pct:
                if not self._spike_firing:
                    self._spike_firing = True
                    alerts.append(Alert(
                        alert_id=f"cost_spike_{self._reading_counter}",
                        name="cost_spike",
                        severity=AlertSeverity.WARNING,
                        state=AlertState.FIRING,
                        message=f"Cost spike: ${current:.4f} is {pct_above:.0f}% above rolling avg ${avg:.4f}",
                        owner=get_owner("cost_spike"),
                        metric_value=current,
                        threshold=avg * (1 + self.spike_threshold_pct / 100),
                    ))
            else:
                if self._spike_firing:
                    self._spike_firing = False
                    alerts.append(Alert(
                        alert_id=f"cost_spike_resolved_{self._reading_counter}",
                        name="cost_spike",
                        severity=AlertSeverity.WARNING,
                        state=AlertState.RESOLVED,
                        message="Cost spike resolved — returned to normal range",
                        owner=get_owner("cost_spike"),
                        metric_value=current,
                        threshold=avg * (1 + self.spike_threshold_pct / 100),
                    ))

            # Sustained increase detection (deduped)
            if pct_above > self.sustained_threshold_pct:
                self._above_count += 1
            else:
                self._above_count = 0
                if self._sustained_firing:
                    self._sustained_firing = False
                    alerts.append(Alert(
                        alert_id=f"cost_sustained_resolved_{self._reading_counter}",
                        name="cost_sustained_increase",
                        severity=AlertSeverity.CRITICAL,
                        state=AlertState.RESOLVED,
                        message="Sustained cost increase resolved",
                        owner=get_owner("cost_sustained_increase"),
                        metric_value=current,
                        threshold=avg * (1 + self.sustained_threshold_pct / 100),
                    ))

            if self._above_count >= self.sustained_count and not self._sustained_firing:
                self._sustained_firing = True
                alerts.append(Alert(
                    alert_id=f"cost_sustained_{self._reading_counter}",
                    name="cost_sustained_increase",
                    severity=AlertSeverity.CRITICAL,
                    state=AlertState.FIRING,
                    message=(
                        f"Sustained cost increase: {self._above_count} consecutive readings "
                        f"above {self.sustained_threshold_pct}% of rolling avg"
                    ),
                    owner=get_owner("cost_sustained_increase"),
                    metric_value=current,
                    threshold=avg * (1 + self.sustained_threshold_pct / 100),
                ))

        return alerts


# ---------------------------------------------------------------------------
# Alert engine
# ---------------------------------------------------------------------------

class AlertEngine:
    """Evaluates SLOs, detects anomalies, routes alerts to handlers."""

    def __init__(
        self,
        handlers: list[AlertHandler] | None = None,
        collector: MetricsCollector | None = None,
    ) -> None:
        self.handlers = handlers or [LogAlertHandler()]
        self.collector = collector or metrics
        self.cost_detector = CostAnomalyDetector()
        self._active_alerts: dict[str, Alert] = {}
        self._history: list[Alert] = []

    def evaluate(self) -> list[Alert]:
        """Run all SLO checks and anomaly detection. Returns new/changed alerts."""
        new_alerts: list[Alert] = []

        # SLO-based alerts
        slo_results = check_all_slos(self.collector)
        for result in slo_results:
            name = result["name"]
            if not result["passing"]:
                if name not in self._active_alerts:
                    alert = Alert(
                        alert_id=f"slo_{name}_{int(time.time())}",
                        name=name,
                        severity=AlertSeverity.CRITICAL if "error" in name or "availability" in name else AlertSeverity.WARNING,
                        state=AlertState.FIRING,
                        message=f"SLO breach: {result['description']} — actual={result['actual']:.4f}, threshold={result['threshold']}",
                        owner=get_owner(name),
                        metric_value=result["actual"],
                        threshold=result["threshold"],
                    )
                    self._active_alerts[name] = alert
                    new_alerts.append(alert)
            else:
                if name in self._active_alerts:
                    resolved = self._active_alerts.pop(name)
                    resolved.state = AlertState.RESOLVED
                    resolved.resolved_at = datetime.now(tz=timezone.utc)
                    new_alerts.append(resolved)

        # Cost anomaly detection
        current_cost = self.collector.get_gauge("llm_cost_total_usd")
        cost_alerts = self.cost_detector.add_reading(current_cost)
        new_alerts.extend(cost_alerts)

        # Deliver all new alerts
        for alert in new_alerts:
            self._history.append(alert)
            for handler in self.handlers:
                handler.handle(alert)

        return new_alerts

    @property
    def active_alerts(self) -> list[Alert]:
        return list(self._active_alerts.values())

    @property
    def history(self) -> list[Alert]:
        return list(self._history)

    def get_status(self) -> dict[str, Any]:
        """Return current alerting status for dashboard."""
        return {
            "active_count": len(self._active_alerts),
            "active_alerts": [a.to_dict() for a in self._active_alerts.values()],
            "total_fired": len(self._history),
            "recent_history": [a.to_dict() for a in self._history[-20:]],
        }
