"""Operations dashboard — metrics, SLOs, cost tracking.

Provides:
- GET /ops/metrics      — raw metrics snapshot (JSON)
- GET /ops/slos         — SLO status with pass/fail
- GET /ops/cost         — cost tracking by stage/project
- GET /ops/dashboard    — HTML dashboard page
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from packages.shared.observability import check_all_slos, metrics

router = APIRouter(prefix="/ops", tags=["operations"])


@router.get("/metrics")
def get_metrics() -> dict[str, Any]:
    """Full metrics snapshot: counters, gauges, histograms with percentiles."""
    return metrics.snapshot()


@router.get("/slos")
def get_slos() -> dict[str, Any]:
    """SLO status for all defined objectives."""
    results = check_all_slos()
    all_passing = all(r["passing"] for r in results)
    return {
        "all_passing": all_passing,
        "slos": results,
    }


@router.get("/cost")
def get_cost() -> dict[str, Any]:
    """Cost tracking: token usage and estimated spend."""
    snapshot = metrics.snapshot()
    return {
        "total_tokens": metrics.get_counter("llm_tokens_total"),
        "total_cost_usd": metrics.get_gauge("llm_cost_total_usd"),
        "by_stage": _extract_labeled("llm_tokens", snapshot.get("counters", {})),
        "by_project": _extract_labeled("project_cost_usd", snapshot.get("gauges", {})),
        "by_run": _extract_labeled("run_cost_usd", snapshot.get("gauges", {})),
    }


def _extract_labeled(prefix: str, data: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for key, value in data.items():
        if key.startswith(prefix + "{"):
            label = key.split("{")[1].rstrip("}")
            result[label] = value
    return result


# ---------------------------------------------------------------------------
# Cost recording helpers (called by analysis/LLM integrations)
# ---------------------------------------------------------------------------

def record_llm_cost(
    tokens: int,
    cost_usd: float,
    stage: str = "unknown",
    project_id: str = "",
    run_id: str = "",
) -> None:
    """Record LLM token usage and cost.

    Called by analysis orchestrator and assistant shell after each LLM call.
    """
    metrics.increment("llm_tokens_total", tokens)
    metrics.increment("llm_tokens", tokens, labels={"stage": stage})
    metrics.increment_gauge("llm_cost_total_usd", cost_usd)
    if project_id:
        metrics.increment_gauge("project_cost_usd", cost_usd, labels={"project": project_id})
    if run_id:
        metrics.increment_gauge("run_cost_usd", cost_usd, labels={"run": run_id})


# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quant Platform — Operations Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #0f172a; color: #e2e8f0; padding: 24px; }
  h1 { font-size: 1.5rem; margin-bottom: 20px; color: #38bdf8; }
  h2 { font-size: 1.1rem; margin: 16px 0 8px; color: #94a3b8; text-transform: uppercase;
       letter-spacing: 0.05em; font-weight: 500; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
  .card { background: #1e293b; border-radius: 12px; padding: 20px; }
  .metric { font-size: 2rem; font-weight: 700; color: #f8fafc; }
  .label { font-size: 0.85rem; color: #64748b; margin-top: 4px; }
  .slo { display: flex; align-items: center; gap: 8px; padding: 6px 0; }
  .slo .dot { width: 10px; height: 10px; border-radius: 50%; }
  .pass { background: #22c55e; }
  .fail { background: #ef4444; }
  .refresh { color: #64748b; font-size: 0.8rem; margin-top: 16px; }
  table { width: 100%; border-collapse: collapse; margin-top: 8px; }
  th, td { text-align: left; padding: 6px 12px; border-bottom: 1px solid #334155; }
  th { color: #94a3b8; font-weight: 500; font-size: 0.85rem; }
</style>
</head>
<body>
<h1>Operations Dashboard</h1>
<div class="grid" id="cards">
  <div class="card"><div class="label">Loading...</div></div>
</div>
<div class="refresh" id="ts"></div>
<script>
async function load() {
  const [health, slos, cost] = await Promise.all([
    fetch('/health/detailed').then(r => r.json()),
    fetch('/ops/slos').then(r => r.json()),
    fetch('/ops/cost').then(r => r.json()),
  ]);
  const h = health.api_health;
  const j = health.job_health;
  const c = cost;
  let html = '';

  // API Health
  html += `<div class="card"><h2>API Health</h2>
    <div class="metric">${h.total_requests}</div><div class="label">Total Requests</div>
    <table><tr><th>p50</th><th>p95</th><th>p99</th><th>Errors</th></tr>
    <tr><td>${h.latency_p50_ms.toFixed(1)}ms</td><td>${h.latency_p95_ms.toFixed(1)}ms</td>
    <td>${h.latency_p99_ms.toFixed(1)}ms</td><td>${h.error_count}</td></tr></table></div>`;

  // Job Health
  html += `<div class="card"><h2>Job Health</h2>
    <div class="metric">${j.completed + j.failed}</div><div class="label">Total Jobs</div>
    <table><tr><th>Completed</th><th>Failed</th><th>Queue Depth</th></tr>
    <tr><td>${j.completed}</td><td>${j.failed}</td><td>${j.queue_depth}</td></tr></table></div>`;

  // SLOs
  html += '<div class="card"><h2>SLOs</h2>';
  for (const s of slos.slos) {
    const cls = s.passing ? 'pass' : 'fail';
    html += `<div class="slo"><span class="dot ${cls}"></span>
      <span>${s.name}: ${s.actual.toFixed(4)} (threshold: ${s.threshold})</span></div>`;
  }
  html += '</div>';

  // Cost
  html += `<div class="card"><h2>Cost</h2>
    <div class="metric">$${c.total_cost_usd.toFixed(4)}</div><div class="label">Total Spend</div>
    <table><tr><th>Tokens</th><td>${c.total_tokens}</td></tr></table></div>`;

  document.getElementById('cards').innerHTML = html;
  document.getElementById('ts').textContent = 'Last updated: ' + new Date().toLocaleTimeString();
}
load();
setInterval(load, 10000);
</script>
</body>
</html>"""


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    """HTML operations dashboard with auto-refresh."""
    return DASHBOARD_HTML
