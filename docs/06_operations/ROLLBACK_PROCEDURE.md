# Rollback Procedure

Step-by-step rollback procedure with timing targets. Validated via
recovery drills (see test suite: `test_migrations_backup.py`).

## When to Rollback

- Health endpoint returns errors after deploy
- Error rate exceeds SLO threshold (> 5%)
- Critical functionality broken (analysis runs, auth, data access)
- Database migration failed partway through

## Timing Targets

| Step | Target | Notes |
|------|--------|-------|
| Decision to rollback | < 5 min | Don't debate — if in doubt, roll back |
| Code rollback | < 2 min | Git tag checkout |
| Migration rollback | < 5 min | Alembic downgrade |
| Database restore (SQLite) | < 5 min | File-level restore |
| Database restore (PostgreSQL) | < 15 min | pg_restore from dump |
| Smoke test verification | < 5 min | Health + core workflow |
| **Total** | **< 30 min** | End-to-end |

## Procedure

### Step 1: Assess (< 5 min)

```bash
# Check health
curl http://localhost:8010/health

# Check error rate via metrics
python -c "
from packages.shared.observability import check_all_slos, metrics
for r in check_all_slos():
    print(f'{r[\"name\"]}: {\"PASS\" if r[\"passing\"] else \"FAIL\"} ({r[\"actual\"]:.4f} vs {r[\"threshold\"]})')
"
```

Decision: If health is down OR any SLO is failing, proceed to rollback.

### Step 2: Code Rollback (< 2 min)

```bash
# Find the last known-good tag
git tag --list 'v*' --sort=-version:refname | head -5

# Checkout the previous version
git checkout v<PREVIOUS_VERSION>

# Reinstall dependencies
pip install -e ".[dev]"
```

### Step 3: Migration Rollback (if needed) (< 5 min)

Only needed if the failed release included a schema migration.

```bash
# Check current migration state
python -c "from packages.shared.db.migrate import get_current_revision; print(get_current_revision())"

# Downgrade one step
python -c "from packages.shared.db.migrate import run_downgrade; run_downgrade(revision='-1')"

# Verify
python -c "from packages.shared.db.migrate import get_current_revision; print(get_current_revision())"
```

### Step 4: Database Restore (if data corrupted) (< 5 min SQLite / < 15 min PostgreSQL)

Only needed if the migration or code change corrupted data.

```bash
# SQLite — restore from backup
python -c "
from packages.shared.db.backup import restore_sqlite
restore_sqlite('backups/pre_release_backup.db', 'data/local.db')
print('Restored.')
"

# Verify integrity
python -c "
from packages.shared.db.backup import verify_integrity
from packages.shared.db.engine import SessionLocal
db = SessionLocal()
result = verify_integrity(db)
print('OK' if result['ok'] else 'INTEGRITY CHECK FAILED')
print(result['row_counts'])
db.close()
"
```

### Step 5: Restart Services (< 2 min)

```bash
# Restart API server
# (if using systemd: sudo systemctl restart quant-api)
# (if using uvicorn directly: kill and restart)
python -m uvicorn apps.api.main:app --port 8010
```

### Step 6: Smoke Test (< 5 min)

```bash
# Health
curl http://localhost:8010/health

# Run critical tests
pytest tests/unit/test_database.py tests/unit/test_auth.py tests/unit/test_api_skeleton.py -v --tb=short

# Verify golden datasets still match
pytest tests/unit/test_golden_datasets.py -v
```

### Step 7: Communicate (< 5 min)

1. Post in team channel: "Rollback complete. Version reverted to vX.Y.Z."
2. File P0/P1 incident (see [OWNERSHIP.md](OWNERSHIP.md#escalation-procedure))
3. Schedule post-mortem within 24 hours

## Pre-Release Backup Checklist

Before every release, take a backup:

```bash
python -c "
from packages.shared.db.backup import backup_sqlite
backup_sqlite('data/local.db', 'backups/pre_release_backup.db')
print('Backup complete.')
"
```

## Drill Schedule

Run a rollback drill quarterly to validate timing targets:

1. Take backup of current state
2. Deploy a test change
3. Execute full rollback procedure
4. Record actual timings
5. Update timing targets if needed
6. Document in ADR if procedure changes

## Recovery Validation Tests

The test suite includes automated recovery drills:

- `tests/unit/test_migrations_backup.py::TestRecoveryDrill` — Full backup/destroy/restore/verify cycle
- `tests/unit/test_golden_datasets.py` — Analysis output stability
- `tests/unit/test_api_compat.py` — API schema backwards compatibility
