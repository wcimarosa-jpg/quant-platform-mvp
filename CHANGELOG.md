# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Sprint CLI scripts for MCP workflow (claude_worker.py, review_manager.py, run_sprint_loop.py)
- Sprint commands reference documentation (SPRINT_COMMANDS.md)

## [0.1.0] - 2026-04-07

### Added
- **P00-P08: Full MVP** — Brief ingestion, questionnaire generation, data mapping, table generation, analysis engine (drivers, segmentation, MaxDiff/TURF), insight narratives, run comparison, exports
- **P09 Hardening** — SQLAlchemy ORM, auth/RBAC (JWT, PBKDF2), job queue with retry/dead-letter, optimistic locking, project data isolation, idempotency keys, Alembic migrations, backup/restore, observability (metrics, SLOs, structured logging), concurrency regression suite
- **P10 Engineering Excellence** — ADR discipline (6 ADRs), plugin contract for analysis methodologies, golden datasets with regression tests, CI quality gates (GitHub Actions, ruff, pyright, pip-audit), API versioning with OpenAPI snapshot compatibility testing, operational runbooks, onboarding playbook, dependency management policy

### Infrastructure
- FastAPI API server with `/api/v1/` versioned routes (21 endpoints)
- SQLite (dev) / PostgreSQL (prod) dual-engine database
- Alembic migration framework with initial schema (10 tables)
- GitHub Actions CI: lint, test, type-check, security-scan, schema-check
- Dependabot for automated dependency updates

### Documentation
- 6 Architecture Decision Records (ADR-001 through ADR-006)
- Operational runbooks (10 procedures)
- Onboarding playbook (9-step setup guide)
- Component ownership and escalation matrix
- Dependency management policy with upgrade checklists
