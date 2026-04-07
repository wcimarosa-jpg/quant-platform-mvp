# Release Process

Standardized procedures for versioning, releasing, and rolling back
the quant platform.

## Semantic Versioning

This project follows [Semantic Versioning 2.0.0](https://semver.org/):

- **MAJOR** (X.0.0): Breaking API changes, incompatible schema migrations
- **MINOR** (0.X.0): New features, non-breaking additions
- **PATCH** (0.0.X): Bug fixes, security patches, documentation

### Version Locations

Version must be updated in sync across:

| File | Field | Example |
|------|-------|---------|
| `pyproject.toml` | `version` | `"0.1.0"` |
| `apps/api/main.py` | FastAPI `version` param | `version="0.1.0"` |
| `CHANGELOG.md` | Release header | `## [0.1.0] - 2026-04-07` |

Use `scripts/check_release.py` to verify version consistency.

## Changelog Process

Every PR that changes user-facing behavior must update `CHANGELOG.md`:

1. Add entries under `## [Unreleased]` in the appropriate category:
   - **Added** — new features
   - **Changed** — changes to existing features
   - **Deprecated** — features to be removed
   - **Removed** — removed features
   - **Fixed** — bug fixes
   - **Security** — vulnerability fixes
2. At release time, rename `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD`
3. Add a new empty `[Unreleased]` section at the top

## Release Checklist

### Pre-Release

- [ ] All CI jobs pass (lint, test, type-check, security-scan, schema-check)
- [ ] Golden dataset regression tests pass
- [ ] API compatibility check passes (no breaking changes vs snapshot)
- [ ] `CHANGELOG.md` updated with release version and date
- [ ] Version bumped in `pyproject.toml` and `apps/api/main.py`
- [ ] `scripts/check_release.py` passes
- [ ] Database backup taken
- [ ] Rollback procedure reviewed

### Release

- [ ] Create git tag: `git tag -a v0.1.0 -m "Release 0.1.0"`
- [ ] Push tag: `git push origin v0.1.0`
- [ ] Run database migrations: `python -c "from packages.shared.db.migrate import run_upgrade; run_upgrade()"`
- [ ] Verify health endpoint: `curl http://localhost:8010/health`
- [ ] Smoke test core workflows

### Post-Release

- [ ] Verify CHANGELOG.md has new `[Unreleased]` section
- [ ] Monitor error rates and latency (check SLOs)
- [ ] Announce release to team

## Rollback Procedure

See [ROLLBACK_PROCEDURE.md](ROLLBACK_PROCEDURE.md) for detailed steps.

Quick reference:
1. Revert to previous git tag: `git checkout v0.0.X`
2. Rollback migrations if needed: `python -c "from packages.shared.db.migrate import run_downgrade; run_downgrade()"`
3. Restore database backup if data corrupted
4. Verify health + run smoke tests
