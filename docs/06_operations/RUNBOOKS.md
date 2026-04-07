# Operational Runbooks

Procedures for common operational tasks and failure recovery.

---

## Table of Contents

1. [Database Migration](#1-database-migration)
2. [Database Backup and Restore](#2-database-backup-and-restore)
3. [Stuck or Failed Jobs](#3-stuck-or-failed-jobs)
4. [API Server Issues](#4-api-server-issues)
5. [Authentication Failures](#5-authentication-failures)
6. [Optimistic Locking Conflicts](#6-optimistic-locking-conflicts)
7. [Analysis Run Failures](#7-analysis-run-failures)
8. [Golden Dataset Drift](#8-golden-dataset-drift)
9. [CI Pipeline Failures](#9-ci-pipeline-failures)
10. [Disaster Recovery](#10-disaster-recovery)

---

## 1. Database Migration

### Running migrations

```bash
python -c "from packages.shared.db.migrate import run_upgrade; run_upgrade()"
```

### Checking migration status

```bash
python -c "
from packages.shared.db.migrate import get_current_revision, get_head_revision, pending_migrations
print(f'Current: {get_current_revision()}')
print(f'Head: {get_head_revision()}')
print(f'Pending: {pending_migrations()}')
"
```

### Rolling back a migration

```bash
python -c "from packages.shared.db.migrate import run_downgrade; run_downgrade(revision='-1')"
```

### Creating a new migration

```bash
# After modifying models.py:
alembic revision --autogenerate -m "Description of schema change"
# Review the generated file in migrations/versions/
# Test: upgrade, verify, downgrade, upgrade again
```

### Troubleshooting: "Target database is not up to date"

1. Check current revision: `get_current_revision()`
2. Check pending: `pending_migrations()`
3. If stuck, verify alembic_version table manually
4. Never delete the alembic_version table — it tracks migration state

---

## 2. Database Backup and Restore

### SQLite backup

```python
from packages.shared.db.backup import backup_sqlite
backup_sqlite("data/local.db", "backups/local_YYYY-MM-DD.db")
```

### JSON dump (cross-engine portable)

```python
from packages.shared.db.engine import SessionLocal
from packages.shared.db.backup import dump_to_file
db = SessionLocal()
dump_to_file(db, "backups/dump_YYYY-MM-DD.json")
db.close()
```

### Restore from backup

```python
from packages.shared.db.backup import restore_sqlite
restore_sqlite("backups/local_2026-04-07.db", "data/local.db")
```

### Restore from JSON dump

```python
from packages.shared.db.engine import SessionLocal
from packages.shared.db.backup import restore_from_file
db = SessionLocal()
counts = restore_from_file(db, "backups/dump.json")
db.commit()
db.close()
print(counts)  # {table: row_count, ...}
```

### Verify integrity after restore

```python
from packages.shared.db.backup import verify_integrity
from packages.shared.db.engine import SessionLocal
db = SessionLocal()
result = verify_integrity(db)
print(result)  # {"ok": True, "tables_found": [...], ...}
db.close()
```

---

## 3. Stuck or Failed Jobs

### Check job queue status

```python
from packages.shared.db.engine import SessionLocal
from packages.shared.job_queue import list_jobs, list_dead_letter
db = SessionLocal()
print("Queued:", len(list_jobs(db, status="queued")))
print("Running:", len(list_jobs(db, status="running")))
print("Failed:", len(list_jobs(db, status="failed")))
print("Dead letter:", len(list_dead_letter(db)))
db.close()
```

### Requeue a failed job

Failed jobs are automatically requeued up to `max_attempts` (default 3).
After exhausting retries, they move to dead letter.

### Investigate dead-letter jobs

```python
from packages.shared.job_queue import list_dead_letter
db = SessionLocal()
for job in list_dead_letter(db):
    print(f"{job.id}: {job.error_type} - {job.error_message}")
db.close()
```

### Common causes

| Symptom | Cause | Fix |
|---------|-------|-----|
| Job stuck in "running" | Worker crashed mid-execution | Restart worker; job will timeout |
| Dead letter: "timeout" | Analysis took > 300s | Increase `timeout_seconds` or optimize |
| Dead letter: "missing_data" | Input DataFrame was empty | Check upstream data pipeline |
| Duplicate job error | Same idempotency key resubmitted | Expected behavior — retrieve existing job |

---

## 4. API Server Issues

### Server won't start

1. Check port availability: `lsof -i :8010` (or `netstat -ano | findstr 8010` on Windows)
2. Check `.env` file exists and has valid `API_PORT`
3. Check dependencies installed: `pip install -e ".[dev]"`

### 500 Internal Server Error

1. Check server logs (stderr output)
2. Common causes:
   - Database not initialized (run migrations)
   - Missing environment variables
   - Import errors from missing dependencies

### 409 Conflict Error

This is expected behavior from optimistic locking. The client should:
1. Refetch the current version
2. Merge changes
3. Retry with the new `version_token`

---

## 5. Authentication Failures

### "Invalid token" error

1. Token may be expired — JWT tokens have a TTL
2. Token may be malformed — check the Authorization header format: `Bearer <token>`
3. In production: verify `JWT_SECRET` is set and consistent across restarts

### "Production JWT secret not configured"

RuntimeError at startup means `JWT_SECRET` env var is not set in a non-dev environment.
Fix: Set `JWT_SECRET` to a strong random value (at least 32 characters).

### Timing-safe authentication

The system uses constant-time comparison to prevent timing attacks.
If authentication seems slow, this is by design (PBKDF2 with 100k iterations).

---

## 6. Optimistic Locking Conflicts

### What it means

Two users tried to edit the same entity (brief, questionnaire, or mapping)
simultaneously. The second write is rejected with a 409 Conflict.

### Resolution

1. Client receives 409 with `current_version` in the response
2. Client refetches the entity to get the latest state
3. Client merges their changes with the latest version
4. Client retries the update with the new `version_token`

### Debugging frequent conflicts

```python
from packages.shared.db.engine import SessionLocal
from packages.shared.optimistic_lock import get_version_token
db = SessionLocal()
print(get_version_token(db, "brief", "brief-123"))
db.close()
```

---

## 7. Analysis Run Failures

### Check run status

```python
from packages.survey_analysis.run_orchestrator import RunStore
store = RunStore()
run = store.get("run-abc12345")
print(run.status, run.error_message, run.error_type)
```

### Common error types

| error_type | Meaning | Fix |
|------------|---------|-----|
| `unknown_analysis_type` | Analysis not registered | Import the analysis module |
| `insufficient_variance` | Data doesn't meet statistical requirements | Check input data quality |
| `missing_data` | Required columns missing from DataFrame | Verify column mapping |
| `unexpected_error` | Unhandled exception | Check full stack trace in logs |

### Re-running a failed analysis

Create a new run with the same configuration. The idempotency system
will prevent exact duplicates — use a new nonce if re-running intentionally:

```python
from packages.shared.idempotency import generate_idempotency_key
key = generate_idempotency_key("proj-1", "drivers", nonce="retry-2")
```

---

## 8. Golden Dataset Drift

### Symptom

`test_golden_datasets.py` fails with tolerance errors.

### Diagnosis

1. Was the analysis code intentionally changed? If yes, regenerate goldens.
2. Was a dependency updated (numpy, scikit-learn)? Dependency updates can
   shift floating-point results.

### Regenerating golden datasets

```bash
python -m data.fixtures.golden.generator
```

Then run regression tests to confirm:

```bash
pytest tests/unit/test_golden_datasets.py -v
```

Commit both the code change and updated golden files together.

---

## 9. CI Pipeline Failures

### Ruff lint failures

```bash
ruff check .          # Show errors
ruff check . --fix    # Auto-fix where possible
ruff format .         # Auto-format
```

### ADR check failures

```bash
python scripts/check_adr.py
```

Common causes: missing required section, bad naming, invalid status.

### Schema compatibility failures

A test in `test_api_compat.py` failed = breaking change detected.

1. Was the change intentional? If yes:
   - Create ADR documenting the breaking change
   - Regenerate the OpenAPI snapshot
   - Bump the API version if needed
2. Was it accidental? Revert the route/model change.

Regenerate snapshot:

```python
from apps.api.main import app
from packages.shared.api_compat import capture_openapi_schema, save_snapshot
save_snapshot(capture_openapi_schema(app))
```

---

## 10. Disaster Recovery

### Full recovery drill (SQLite)

```bash
# 1. Backup current database
python -c "from packages.shared.db.backup import backup_sqlite; backup_sqlite('data/local.db', 'backups/dr_backup.db')"

# 2. Verify backup integrity
python -c "
from packages.shared.db.backup import verify_integrity
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
engine = create_engine('sqlite:///backups/dr_backup.db')
db = sessionmaker(bind=engine)()
print(verify_integrity(db))
db.close()
"

# 3. Restore (if needed)
python -c "from packages.shared.db.backup import restore_sqlite; restore_sqlite('backups/dr_backup.db', 'data/local.db')"
```

### Recovery checklist

- [ ] Identify scope of data loss
- [ ] Locate most recent backup (check `backups/` directory)
- [ ] Verify backup integrity before restoring
- [ ] Restore to a temporary location first to validate
- [ ] Restore to production location
- [ ] Run migration check: `is_up_to_date()`
- [ ] Run integrity check: `verify_integrity()`
- [ ] Notify team via escalation path
