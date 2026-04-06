# ADR-003: Storage Architecture

**Status:** Accepted
**Date:** 2026-04-06
**Ticket:** P09-01, P09-07

## Context

The platform needs persistent storage for projects, briefs, questionnaires,
mappings, analysis runs, users, and audit logs. Development requires fast
local iteration; production requires reliability, concurrent access, and
backup/restore capabilities.

## Decision

### Dual-engine strategy: SQLite (dev) + PostgreSQL (prod)

- **SQLAlchemy 2.0 ORM** as the single abstraction layer (`packages/shared/db/`)
- **SQLite with WAL mode** for development and testing — zero-config, file-based
- **PostgreSQL** for production — connection pooling, row-level locking, ACID
- **Alembic** for schema migrations — same migration files work on both engines
- **`DATABASE_URL`** env var switches between engines transparently

### Schema design

- All entities use string primary keys (`String(64)`) for cross-system compatibility
- `version_token` (integer) on mutable entities for optimistic locking
- `idempotency_key` (unique, nullable) on `AnalysisRunRow` and `JobRow` for dedup
- `project_id` foreign key on all project-scoped entities with `CASCADE` delete
- JSON columns for flexible payloads (`config_json`, `sections_json`, `mappings_json`)

### Backup and recovery

- SQLite: file-level backup via `sqlite3.backup()` API (consistent snapshots)
- Cross-engine: JSON dump/restore for portability
- Integrity verification with FK checks post-restore

## Alternatives Considered

| Alternative | Pros | Cons | Why not chosen |
|------------|------|------|----------------|
| PostgreSQL only | Single engine, no branching | Requires Docker/server for dev | Slows local iteration |
| Raw SQL | No ORM overhead | No migration support, manual mapping | Unmaintainable at scale |
| MongoDB | Flexible schema | No FK enforcement, weak transactions | Platform needs referential integrity |
| File-based JSON | Simplest | No concurrent access, no indexing | Already outgrown by P03 |

## Consequences

- All DB access goes through `packages/shared/db/repository.py` — no raw SQL in routes
- Schema changes require an Alembic migration + test
- SQLite limitations (no `FOR UPDATE`) handled with graceful fallbacks
- `get_db()` dependency handles commit/rollback lifecycle — callers never commit

## References

- `packages/shared/db/engine.py` — engine configuration
- `packages/shared/db/models.py` — ORM models
- `packages/shared/db/repository.py` — CRUD operations
- `packages/shared/db/backup.py` — backup/restore utilities
- `packages/shared/db/migrate.py` — programmatic Alembic interface
- `migrations/versions/001_initial_schema.py` — initial migration
