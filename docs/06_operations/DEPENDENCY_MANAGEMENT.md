# Dependency and Upgrade Management Policy

## Update Cadence

| Category | Frequency | Method |
|----------|-----------|--------|
| Security patches | Immediate (< 24h) | Dependabot auto-PR + manual review |
| Minor/patch updates | Weekly (Monday) | Dependabot grouped PRs |
| Major version bumps | Quarterly review | Manual PR with compatibility testing |
| Python version | Annual | Manual upgrade with full regression |

## Automated Updates

### Dependabot

Configured in `.github/dependabot.yml`:
- **pip**: Weekly on Mondays, max 5 open PRs, minor/patch grouped
- **GitHub Actions**: Weekly on Mondays, max 3 open PRs
- Labels: `dependencies` + `automated` for pip, `ci` + `automated` for Actions

### Security Scanning

`pip-audit` runs in CI on every push and PR:
- Checks installed packages against the Python Advisory Database
- `--strict` flag fails the build on any known vulnerability
- `--desc` flag includes vulnerability descriptions for triage

## Upgrade Checklist

Use this checklist when upgrading any dependency:

### Minor/Patch Updates (low risk)

- [ ] Review Dependabot PR diff — check changelog for breaking changes
- [ ] CI passes (lint, test, type-check, schema-check, security-scan)
- [ ] Golden dataset regression tests pass (`test_golden_datasets.py`)
- [ ] Merge

### Major Version Bumps (high risk)

- [ ] Read the library's migration guide / changelog
- [ ] Check if the package is in the high-risk list (see below)
- [ ] Create a branch: `deps/upgrade-<package>-<version>`
- [ ] Update version constraint in `pyproject.toml`
- [ ] Run full test suite locally: `pytest --tb=short -q`
- [ ] Run golden dataset regression: `pytest tests/unit/test_golden_datasets.py -v`
- [ ] Run API compatibility check: `pytest tests/unit/test_api_compat.py -v`
- [ ] If golden outputs changed: regenerate with `python -m data.fixtures.golden.generator`
- [ ] If API schema changed: regenerate with `save_snapshot(capture_openapi_schema(app))`
- [ ] Document any code changes needed in the PR description
- [ ] If breaking: write an ADR explaining the upgrade rationale
- [ ] CI passes all jobs
- [ ] Get reviewer approval
- [ ] Merge

### Rollback Procedure

If an upgrade causes issues after merge:

1. `git revert <merge-commit>` — revert the dependency change
2. Run `pip install -e ".[dev]"` to restore previous versions
3. Verify: `pytest --tb=short -q`
4. Push revert commit
5. File an issue documenting what broke and why

## High-Risk Packages

These packages have large API surfaces or affect core behavior.
Major version bumps require the full checklist above:

| Package | Risk Area | What to Watch |
|---------|-----------|---------------|
| `sqlalchemy` | Database layer | Session API, query syntax, type system |
| `pydantic` | All models | Validator API, serialization, model_validate |
| `fastapi` | API layer | Depends injection, middleware, OpenAPI generation |
| `alembic` | Migrations | Config format, env.py interface, autogenerate |
| `numpy` | Numeric precision | Float behavior, random API, array creation |
| `pandas` | Data processing | DataFrame API, type inference, copy semantics |
| `scikit-learn` | Analysis results | Algorithm defaults, random state, API changes |

## Version Constraint Policy

All dependencies in `pyproject.toml` must use version constraints:

- **`>=X.Y.Z`**: Minimum version (preferred for most packages)
- **`>=X.Y.Z,<X+1.0.0`**: Range pin (for high-risk packages after testing)
- **`==X.Y.Z`**: Exact pin (only for packages with known compatibility issues)

Never use bare package names without version constraints.

## Security Response

When `pip-audit` or Dependabot flags a vulnerability:

1. **Assess severity**: Check CVSS score and whether our usage is affected
2. **Patch immediately** (< 24h) for Critical/High CVEs in production paths
3. **Schedule for next sprint** for Medium/Low CVEs or dev-only dependencies
4. **Document** in PR description: CVE ID, affected package, upgrade path
