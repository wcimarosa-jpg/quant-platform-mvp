# Docker Smoke Test Report

**Date:** 2026-04-08
**Environment:** Windows 11 host, Docker Desktop 4.68.0, WSL2 backend, x86_64
**Engine:** Docker 29.3.1 (Linux containers)
**Tester:** Solo dev + Claude

## Executive summary

**Verdict: GO for first researcher session.** The full demo path (Login → Project → Brief → Survey → Mapping → Analysis → Report) works end-to-end through `docker compose up` against a non-trivial 500-row CSV. Three blockers were found and fixed during the smoke test (all packaging-level, none affected runtime). Four feature gaps were logged but are non-blocking for a guided demo.

## What was tested

A clean-state walk-through using `docker compose down -v && docker compose build && docker compose up -d`, then a real workflow against the running stack:

1. Container build (Python 3.12 + Node 20 + nginx Alpine, multi-stage)
2. Container startup (API + frontend, with healthcheck and `depends_on: service_healthy`)
3. Nginx routing (SPA fallback, `/api/v1/*` proxy, `/ops/*` proxy, `/health` proxy)
4. User seeding (`scripts/seed_users.py` against the persisted SQLite volume)
5. Login flow (POST `/api/v1/auth/login` through nginx → JWT)
6. Project create/list (DB-backed, scoped to authenticated user)
7. Brief upload (multipart, markdown), GET, PATCH per-field, analyze
8. Methodology list, draft create with pre-selected sections
9. Table generation from a real CSV (RFC 4180 with BOM, quoted commas, escaped quotes, embedded newlines)
10. QA report generation
11. Persistence sanity check across `docker compose restart api`

## Issues found

### Build blockers (fixed during the test)

| # | Issue | Root cause | Fix |
|---|---|---|---|
| 1 | `docker compose up` fails: `env file .env not found` | `.env` not committed (correct) but no setup step copies it | One-line fix: `cp .env.example .env`. Documented in DEMO.md prerequisites. |
| 2 | `RUN npm ci` fails inside frontend-build stage with `Missing: @emnapi/core@1.9.2 from lock file` | Cross-platform optional dep drift: lockfile generated on Windows lacks Linux-specific optional deps for `@napi-rs/wasm-runtime` | Switched Dockerfile from `npm ci` (strict) to `npm install --no-audit --no-fund` (lenient). Slower (~10s extra) but tolerates host-platform drift. Comment in Dockerfile explains. |
| 3 | `RUN pip install --no-cache-dir .` fails with `Multiple top-level packages discovered in a flat-layout` | Repo has 10+ top-level dirs (`apps`, `packages`, `mcp`, `ops`, `data`, `services`, etc.); setuptools auto-discovery refuses to guess | Added `[tool.setuptools] packages = [...]` to `pyproject.toml` with explicit allowlist (`apps`, `apps.api`, `apps.api.routes`, `packages`, `packages.shared`, `packages.shared.db`, `packages.survey_analysis`). |

### Runtime issues found (logged, not yet fixed)

| # | Severity | Issue | Disposition |
|---|---|---|---|
| 4 | Major | Brief parser only extracts `constraints` from a clean markdown brief, missing objectives/audience/category/geography | Brief parser is heuristic-based; will be revisited as part of P12-04 LLM integration |
| 5 | Major | `/ops/cost` reports `total_tokens: 0`, `total_cost_usd: 0.0` after a real workflow | Expected. No LLM calls happen yet (P12-04 gap). Table generator does not self-report compute cost. |
| 6 | **Major** | `/health/detailed` SLO actuals are all `0.0` even after multiple real HTTP requests | The `record_request()` infrastructure exists in `packages/shared/observability.py` but no FastAPI middleware calls it. SLO dashboard will be permanently empty until a middleware is added. |
| 7 | Major | In-memory stores (briefs, drafts, table runs, QA reports) wiped on `docker compose restart api` — only projects survive | Known. Tracked as P12-03 (DB persistence migration). Mitigated for the demo by `DEMO.md` warning. |

### Things that worked first try

- Multi-stage Dockerfile produces both images cleanly (after fixes above)
- `depends_on: service_healthy` correctly blocks frontend startup until API healthcheck passes
- Nginx SPA fallback (`try_files $uri $uri/ /index.html`) — every deep route serves the React shell
- Nginx upstream proxying for `/api/v1/*`, `/ops/*`, `/health` — backend reachable via the frontend port
- JWT auth round-trip through the proxy
- Resource-level authorization on briefs / drafts / tables (the post-Codex-review fix)
- The CSV parser + column profiler + table_types selection (the post-Codex-blocker fix)
- 500-row demo CSV with BOM, quoted commas, escaped quotes, embedded newlines → 6 tabulatable variables → **12 tables generated, 0 QA errors**

## Files added or modified by the smoke test

| File | Change |
|---|---|
| `.gitignore` | Added `*.db` (smoke-test stray DBs) and `.smoke_*` (scratch files) |
| `Dockerfile` | `npm ci` → `npm install --no-audit --no-fund` with explanatory comment |
| `pyproject.toml` | Added `[tool.setuptools] packages = [...]` allowlist |
| `data/demo_survey.csv` | New: 500-row synthetic CSV stress-testing the RFC 4180 parser |
| `DEMO.md` | New: ~10-minute researcher walkthrough script with troubleshooting |
| `docs/06_operations/SMOKE_TEST_REPORT.md` | This file |

## Go/no-go call

**GO** for first researcher session under the following conditions:

1. **Use the demo CSV provided** (`data/demo_survey.csv`). Don't let the researcher upload their own file in session 1 — the brief parser quality (Issue #4) will undermine confidence before they see the rest of the workflow.
2. **Set expectations up-front**: "The assistant panel responses are stubbed in this preview. We're testing the workflow, not the AI quality."
3. **Don't restart the container mid-session** — briefs/drafts/runs are in-memory and would vanish (Issue #7).
4. **Have `DEMO.md` open** during the session as a reference if anything is unclear.
5. **Schedule the session within 1 week** — the demo path is in a known-good state right now; every additional unrelated change adds drift.

The four feature gaps logged above are real, but **none of them are critical for a workflow-feedback session**. The first session should focus on:
- Does the screen sequence match how a researcher thinks about their work?
- Is the mapping page comprehensible on a real CSV?
- Where do they get stuck or confused?
- What do they expect to see that isn't there?

**Closing notes**: This smoke test consumed roughly 90 minutes total (15 min Docker install troubleshooting, 20 min build/fix iteration, 15 min walkthrough, 30 min logging + writing this report, 10 min demo CSV prep). Codex's prediction that this would take "a focused half-day" was accurate. The three blockers it surfaced were exactly the kind of "demo-day detonation" risk Codex warned about — none of them were caught by the 1671 backend tests, and all three would have surfaced in front of a researcher if not caught here.
