# Architecture Decision Records — Contribution Rules

## When to write an ADR

An ADR is required when a change:

1. **Introduces or replaces** a technology, framework, or library (e.g., switching from SQLite to PostgreSQL)
2. **Changes system boundaries** — adds a new service, splits a module, or alters the API surface
3. **Modifies the data model** in a way that affects multiple modules (e.g., new FK relationships, schema migrations)
4. **Sets a pattern** that future code should follow (e.g., "all analysis functions must use @register_analysis")
5. **Descopes or defers** planned functionality with rationale

An ADR is NOT needed for:

- Bug fixes, minor refactors, or code style changes
- Adding tests or documentation
- Routine dependency updates (unless major version with breaking changes)

## How to write an ADR

1. Copy `ADR-TEMPLATE.md` to `ADR-NNN-short-title.md` (next sequential number)
2. Fill in all sections — Context, Decision, Alternatives, Consequences
3. Set Status to `Proposed`
4. Include the ADR reference in your PR description
5. After review approval, set Status to `Accepted`

## Numbering

- ADRs are numbered sequentially: ADR-001, ADR-002, ADR-003, ...
- Never reuse a number, even if the ADR is deprecated
- Use `Superseded by ADR-NNN` status when replacing an older decision

## Review process

- ADRs are reviewed alongside the implementation PR
- At least one reviewer must approve the ADR before it is accepted
- Disputed decisions should remain `Proposed` until consensus

## CI enforcement

The `scripts/check_adr.py` script verifies:
- All ADR files follow the naming convention `ADR-NNN-*.md`
- Required sections are present (Status, Date, Context, Decision, Consequences)
- No gaps in numbering (warnings only)
- PRs touching architecture files should reference an ADR (advisory)

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [001](ADR-001-assistant-context-contract.md) | Assistant Context Contract | Accepted | 2026-04-02 |
| [002](ADR-002-p07-descope-decisions.md) | P07 Descope Decisions | Accepted | 2026-04-03 |
| [003](ADR-003-storage-architecture.md) | Storage Architecture | Accepted | 2026-04-06 |
| [004](ADR-004-analysis-runtime.md) | Analysis Runtime | Accepted | 2026-04-06 |
| [005](ADR-005-auth-rbac.md) | Authentication and RBAC | Accepted | 2026-04-06 |
| [006](ADR-006-api-versioning.md) | API Versioning and Schema Compatibility | Accepted | 2026-04-07 |
