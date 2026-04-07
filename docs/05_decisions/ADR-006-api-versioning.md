# ADR-006: API Versioning and Schema Compatibility Policy

**Status:** Accepted
**Date:** 2026-04-07
**Ticket:** P10-05

## Context

The platform exposes REST APIs consumed by the React frontend and
potentially external integrations. As the platform evolves, API changes
must not break existing clients. We need a versioning strategy that
balances simplicity (MVP) with future flexibility.

## Decision

### URL-path versioning

All API routes are prefixed with `/api/v{N}` (e.g., `/api/v1/briefs`).
This is the simplest scheme to implement, test, and document. FastAPI's
router prefix system supports this natively.

**Version lifecycle:**
- **Current:** Only `v1` exists during MVP
- **New version:** When breaking changes are needed, mount a `v2` router
  alongside `v1`. Both run simultaneously during a deprecation window.
- **Deprecation:** Deprecated versions return a `Deprecation` header for
  at least 2 release cycles before removal.

### What constitutes a breaking change

**Breaking (requires version bump):**
- Removing or renaming an endpoint
- Removing or renaming a required request field
- Removing a response field that clients depend on
- Changing the type of an existing field
- Changing error response structure

**Non-breaking (safe within same version):**
- Adding optional request fields (with defaults)
- Adding new response fields
- Adding new endpoints
- Adding new enum values (if clients handle unknown values)
- Relaxing validation constraints

### Shared contract versioning

Internal contracts (e.g., `AssistantContext`, result schemas, plugin metadata)
use semver-style `schema_version` fields. The same breaking/non-breaking
rules apply. Schema version is validated on deserialization.

### Schema compatibility testing

- **OpenAPI snapshot:** The API's OpenAPI schema is exported as JSON and
  committed to `data/fixtures/golden/openapi_snapshot.json`.
- **Regression test:** A CI test compares the current OpenAPI schema against
  the snapshot, flagging any removed endpoints or fields as failures.
- **Snapshot update workflow:** When intentional changes are made, the
  developer regenerates the snapshot and includes a migration note.

### Breaking change process

1. Create an ADR explaining the change and rationale
2. Bump the API version (mount new router prefix)
3. Update the OpenAPI snapshot
4. Add migration notes to `CHANGELOG.md`
5. Set `Deprecation` header on the old version

## Alternatives Considered

| Alternative | Pros | Cons | Why not chosen |
|------------|------|------|----------------|
| Header versioning (Accept) | Clean URLs | Harder to test, less visible | URL versioning is simpler for MVP |
| Query param versioning | Easy to add | Pollutes query string, caching issues | Non-standard |
| No versioning | Simplest | Breaking changes break clients | Unacceptable for production |

## Consequences

- All API endpoints live under `/api/v1/` (already the case)
- Breaking changes require a new version prefix and deprecation plan
- OpenAPI snapshot catches accidental breaking changes in CI
- Non-breaking additions are safe and don't require version bumps

## References

- `apps/api/main.py` — Router mounting with version prefix
- `packages/shared/api_compat.py` — Schema compatibility utilities
- `data/fixtures/golden/openapi_snapshot.json` — Baseline API schema
- `tests/unit/test_api_compat.py` — Compatibility regression tests
