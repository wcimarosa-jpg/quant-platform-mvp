# QualatScale Engineering Onboarding Brief

## 1) What This System Is
QualatScale is an AI-powered mixed-method research platform that supports:
- Respondent interview sessions (text, voice/video pathways).
- Guide-driven moderator flows and branching.
- Qualitative analysis pipelines (schema generation, coding, report generation).
- Admin/ops monitoring and telemetry for reliability.

The codebase is split into a FastAPI backend and a Vite/React frontend, with PostgreSQL in production (SQLite used heavily for local/dev tests).

## 2) Repository Layout
- `ai-interview-tool/backend/`
  - FastAPI app, API routes, services, SQLAlchemy models, migrations.
- `ai-interview-tool/frontend/`
  - React app (Vite), interview UI, analysis UI, hooks, Playwright E2E specs.
- `ai-interview-tool/config/`
  - Environment-driven settings and prompt assets.
- `ai-interview-tool/Documentation/`
  - Runbook, implementation plans, rollout docs, operational checklists.
- `.github/workflows/ci.yml`
  - CI pipeline (migration validation, backend tests, frontend build, deployment readiness summary).

## 3) Runtime Architecture

### Backend (FastAPI)
Entry point: `backend/main.py`

Core runtime behavior:
1. Load settings from environment.
2. Initialize observability (Sentry if configured).
3. Run startup lifecycle:
   - Ensure DB schema/tables.
   - Start video processing queue.
   - Start analysis queue worker if enabled (`analysis_queue_enabled=true`).
4. Register API routers (auth, projects, interviews, analysis, admin, telemetry, etc.).
5. Serve health and detailed health endpoints.

Key backend layers:
- Routes: `backend/api/routes/*`
- Dependencies/auth/access control: `backend/api/dependencies.py`, `backend/api/deps_auth.py`, `backend/api/routes/auth.py`
- Services: `backend/services/*`
- Models/DB: `backend/models/*`
- Migrations: `backend/migrations/*.sql`

### Frontend (React + Vite)
Entry/build tooling in `frontend/package.json`.

Core concerns:
- Interview experience (mixed-method, voice/video components).
- Guide-state and reliability behavior in hooks/components.
- Analysis tab UX and status polling.
- E2E testing with Playwright (`frontend/e2e/*`, `frontend/playwright.config.js`).

## 4) Core Functional Domains

### A) Interview Execution
Primary components and routes orchestrate:
- Project-based interview initiation.
- Consent and respondent flow.
- Message/turn handling.
- Guide state progression for mixed-method surveys.

### B) Qualitative Analysis Pipeline
Primary route surface: `backend/api/routes/qualitative_analysis.py`

High-level stages:
1. Schema generation/approval.
2. Manifest coding run creation and execution.
3. Report generation and download.

Pipeline resilience/reliability features currently in repo include:
- DB-backed analysis queue (`analysis_jobs`) for async processing.
- Startup orphan sweep for stale jobs.
- Queue metrics endpoints for admin monitoring.
- Kill switch: `analysis_queue_enabled=false` fallback behavior.

### C) Admin + Reliability Telemetry
- Admin route module: `backend/api/routes/admin.py`
- Telemetry route module: `backend/api/routes/telemetry.py`
- Telemetry persistence model/table: `telemetry_events`

Used for:
- Queue metrics and job inspection.
- Operational and reliability visibility.
- Client event aggregation (where frontend instrumentation exists).

## 5) Data and Persistence

### Database
- Local/dev: SQLite (async via `aiosqlite`).
- Production: PostgreSQL (async via `asyncpg`).

DB setup module: `backend/models/database.py`

Notable persistence entities:
- `projects`, `interviews`, transcript/response entities.
- `analysis_jobs` (queue state, attempts, heartbeat, errors, status timeline).
- `telemetry_events` (reliability event capture).

Migrations:
- SQL migration files in `backend/migrations/`.
- Helper scripts exist for migration workflows and checks.

## 6) Infrastructure and Deployment Model

### Backend Hosting: Railway
- Railway hosts the FastAPI backend service.
- Production secrets and runtime env vars are managed in Railway.
- Typical deploy source: main branch deploy flow.

### Frontend Hosting: Vercel
- Vercel hosts the React/Vite frontend.
- Frontend deploys independently of backend.
- Environment variables (including API base URLs and feature flags) are managed in Vercel.

### Data/Storage/External Services
- PostgreSQL for production persistence.
- Anthropic Claude API for core LLM behavior.
- Deepgram/OpenAI integrations for voice/audio pathways.
- Cloudflare R2 references exist for media storage workflows.
- Optional Sentry integration for backend exception monitoring.

## 7) Configuration Model
Central settings: `config/settings.py`

Important classes of config:
- Environment and debug mode.
- API keys/secrets (`ANTHROPIC_API_KEY`, `JWT_SECRET`, media keys).
- DB URL and pool tuning.
- Queue controls (`analysis_queue_enabled`, concurrency, attempts, heartbeat thresholds).
- Pipeline parameters and limits.
- CORS and frontend origin behavior.

## 8) CI/CD and Quality Gates
Current CI workflow: `.github/workflows/ci.yml`

Jobs include:
1. Migration validation.
2. Backend test job.
3. Frontend build.
4. Deployment readiness summary on `main`.

Testing layers used in this repo:
- Backend pytest suites (`backend/tests/`, plus legacy `tests/`).
- Frontend Playwright E2E reliability specs.
- Local linting (ruff) and type/lint checks where configured.

## 9) Operations and Runbook Expectations
Primary runbook: `Documentation/RUNBOOK.md`

Operational controls documented there include:
- Required production env vars.
- One-time migration notes.
- Auth/JWT setup ordering requirements.
- Analysis queue operations, health checks, and rollback.
- Deployment checklist and post-deploy verification.

Critical operational concept:
- The analysis queue kill switch (`ANALYSIS_QUEUE_ENABLED=false`) is the first-line mitigation if queue behavior threatens UX.

## 10) Security and Access Control Notes
- API access uses dependency-based auth and role checks.
- Project-level access control is dependency-driven in analysis/project paths.
- Admin endpoints should be treated as privileged and require explicit admin dependency enforcement.
- JWT secret configuration is a hard deployment prerequisite.

## 11) Local Development Quick Start
1. Backend
   - Create venv and install `requirements.txt`.
   - Set `.env` values (at minimum app secrets + Anthropic key).
   - Start: `uvicorn backend.main:app --reload --port 8000`.
2. Frontend
   - `cd frontend && npm install`.
   - Start: `npm run dev`.
3. Tests
   - Backend: `python -m pytest backend/tests/ -m "not external and not integration" -q --tb=short`
   - Frontend E2E: `npx playwright test` (from `frontend/`).

## 12) High-Value Orientation Path for a New Engineer
Week 1 recommended order:
1. Read `Documentation/RUNBOOK.md` and this brief.
2. Trace startup path in `backend/main.py`.
3. Walk auth + dependency model (`backend/api/dependencies.py`, `backend/api/routes/auth.py`).
4. Trace one interview flow route + service pair.
5. Trace analysis queue + analysis routes.
6. Run local fast gate tests.
7. Inspect CI workflow and release expectations.

## 13) Current Practical Constraints to Keep in Mind
- Some test suites are categorized as integration/external and may require live services.
- Reliability and moderation hardening work is phased; check active release branch/PR state before broad refactors.
- Production safety decisions should be gate-driven (staging E2E, auth regression checks, queue health checks).

---
This document is intended as an engineering onboarding brief, not a product roadmap. For sprint-level decisions, use active PRs, runbook updates, and current release gate docs as source of truth.
