# Onboarding Playbook

Step-by-step guide for a new engineer to set up the quant platform
locally and run core workflows end-to-end.

## Prerequisites

- **Python 3.11+** (3.12 recommended)
- **Git**
- **pip** (or uv/pipx)
- Editor with Python support (VS Code recommended)

## 1. Clone and install

```bash
git clone https://github.com/wcimarosa-jpg/quant-platform-mvp.git
cd quant-platform-mvp

# Install all dependencies (core + dev)
pip install -e ".[dev]"
```

Verify installation:

```bash
python -c "import fastapi, sqlalchemy, pandas, sklearn; print('OK')"
```

## 2. Environment setup

```bash
cp .env.example .env
```

Edit `.env` and set:

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `APP_ENV` | No | `local` | Set to `production` for prod guards |
| `API_HOST` | No | `127.0.0.1` | |
| `API_PORT` | No | `8010` | |
| `DATABASE_URL` | No | `sqlite:///./data/local.db` | PostgreSQL URL for prod |
| `OPENAI_API_KEY` | Yes (for LLM features) | — | Get from team lead |
| `JWT_SECRET` | Prod only | dev default | Must be set in production |

## 3. Database initialization

```bash
# Run Alembic migrations to create all tables
python -c "from packages.shared.db.migrate import run_upgrade; run_upgrade()"
```

Verify:

```bash
python -c "from packages.shared.db.migrate import is_up_to_date; print('Up to date:', is_up_to_date())"
```

## 4. Run tests

```bash
# Full test suite (should take ~60-90 seconds)
pytest --tb=short -q

# Quick smoke test (just core modules)
pytest tests/unit/test_database.py tests/unit/test_auth.py -v
```

Expected: 1400+ tests passing, 0 failures.

## 5. Start the API server

```bash
python -m uvicorn apps.api.main:app --reload --port 8010
```

Verify: Open http://localhost:8010/docs for the interactive API documentation.

Health check:

```bash
curl http://localhost:8010/health
# {"ok": true, "service": "quant-platform-api", "version": "0.1.0"}
```

## 6. Run the CI quality gates locally

```bash
# Lint
ruff check .
ruff format --check .

# ADR validation
python scripts/check_adr.py

# Quality gates
python scripts/check_ci_gates.py
```

## 7. Key directories

| Directory | Purpose |
|-----------|---------|
| `apps/api/` | FastAPI application and route handlers |
| `packages/shared/` | Core infrastructure (DB, auth, jobs, locking, observability) |
| `packages/survey_analysis/` | Analysis methodologies (drivers, segmentation, MaxDiff) |
| `migrations/` | Alembic database migrations |
| `data/fixtures/` | Test fixtures and golden datasets |
| `docs/` | Product docs, ADRs, operations |
| `scripts/` | CI and utility scripts |
| `tests/` | Test suite |

## 8. Core workflows

### Running an analysis (programmatic)

```python
from packages.survey_analysis.run_orchestrator import (
    AnalysisRun, RunConfig, RunVersions, execute_run,
)
import packages.survey_analysis.drivers  # register plugin

run = AnalysisRun(
    project_id="my-project",
    config=RunConfig(analysis_type="drivers"),
    versions=RunVersions(
        questionnaire_id="q1", questionnaire_version=1,
        mapping_id="m1", mapping_version=1, data_file_hash="abc",
    ),
)
result = execute_run(run, df=my_dataframe, iv_cols=[...], dv_cols=[...])
print(result.status, result.result_summary)
```

### Adding a new analysis plugin

See `packages/survey_analysis/plugin_contract.py` and the smoke test
template in `tests/unit/test_plugin_contract.py::TestNewMethodologySmokeTest`.

### Creating a database backup

```python
from packages.shared.db.backup import backup_sqlite
backup_sqlite("data/local.db", "backups/local_2026-04-07.db")
```

## 9. Getting help

- **ADRs:** `docs/05_decisions/` — architecture decisions and rationale
- **API docs:** http://localhost:8010/docs (when server is running)
- **Operations:** `docs/06_operations/` — runbooks and escalation
- **Tests:** Best documentation is the test suite — read the test names
