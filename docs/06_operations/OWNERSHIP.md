# Ownership and Escalation

Team roles, component ownership, and escalation paths for the quant platform.

## Component Ownership

| Component | Owner | Backup | Description |
|-----------|-------|--------|-------------|
| API Server (`apps/api/`) | Platform Team | — | FastAPI routes, middleware, error handling |
| Database (`packages/shared/db/`) | Platform Team | — | Models, migrations, engine, backup/restore |
| Auth & RBAC (`packages/shared/auth.py`) | Platform Team | — | JWT, passwords, roles, project membership |
| Job Queue (`packages/shared/job_queue.py`) | Platform Team | — | Async execution, retry, dead-letter |
| Drivers Analysis (`packages/survey_analysis/drivers.py`) | Research Team | — | Ridge regression, Pearson, weighted-effects |
| Segmentation (`packages/survey_analysis/segmentation.py`) | Research Team | — | VarClus + KMeans clustering pipeline |
| MaxDiff/TURF (`packages/survey_analysis/maxdiff_turf.py`) | Research Team | — | Count-based scoring, TURF optimization |
| Plugin Contract (`packages/survey_analysis/plugin_contract.py`) | Platform Team | — | Analysis plugin interface and registry |
| CI/CD (`.github/workflows/`) | Platform Team | — | Lint, test, type-check, schema-check |
| Observability (`packages/shared/observability.py`) | Platform Team | — | Metrics, SLOs, structured logging |
| MCP Coordinator | Platform Team | — | Sprint coordination (separate repo) |

## Escalation Paths

### Severity Levels

| Level | Definition | Response Time | Examples |
|-------|-----------|---------------|----------|
| **P0 — Critical** | Service down, data loss risk | Immediate | DB corruption, auth bypass, API unreachable |
| **P1 — High** | Major feature broken | < 4 hours | Analysis runs failing, job queue stuck |
| **P2 — Medium** | Feature degraded | < 1 business day | Slow queries, flaky tests, CI failures |
| **P3 — Low** | Minor issue | Next sprint | UI polish, docs update, code cleanup |

### Escalation Procedure

1. **Identify** — Check runbooks for known resolution
2. **Diagnose** — Gather logs, error messages, reproduction steps
3. **Fix or escalate** — If the issue matches a runbook, follow it. Otherwise:
   - P0/P1: Notify team lead immediately (Slack/Teams/phone)
   - P2: File a ticket, assign to component owner
   - P3: Add to backlog
4. **Post-mortem** — For P0/P1 incidents, write an ADR documenting:
   - What happened
   - Root cause
   - What was done to fix it
   - What will prevent recurrence

### On-Call Rotation

During MVP phase, on-call is not formally scheduled. All team members
should be reachable during business hours. For after-hours P0 issues,
contact the team lead directly.

## Decision Authority

| Decision Type | Authority | Process |
|--------------|-----------|---------|
| Architecture changes | Team consensus via ADR | Write ADR, review in PR |
| New analysis methodology | Research Team + Platform review | Plugin contract + tests |
| Database schema changes | Platform Team | Migration + ADR if breaking |
| API breaking changes | Platform Team + stakeholder sign-off | ADR-006 process |
| Dependency upgrades | Any engineer | PR with test validation |
| Production deployment | Team lead approval | CI green + manual review |

## Key Contacts

| Role | Responsibility |
|------|---------------|
| **Team Lead** | Final escalation, production deployment approval |
| **Platform Engineer** | Infrastructure, database, CI/CD, auth |
| **Research Engineer** | Analysis methodologies, statistical validation |
| **QA/Reviewer** | Test coverage, golden dataset maintenance |
