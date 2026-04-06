# ADR-005: Authentication and Role-Based Access Control

**Status:** Accepted
**Date:** 2026-04-06
**Ticket:** P09-02, P09-05

## Context

The platform is multi-tenant: multiple projects with separate teams. Users need
authentication, role-based permissions, and strict data isolation between projects.
The MVP must support this without external identity providers (Auth0, Cognito) to
keep the dependency footprint minimal.

## Decision

### Authentication

- **PBKDF2-SHA256** password hashing (100k iterations, random salt) — no bcrypt dependency
- **HMAC-SHA256 JWT** tokens for stateless API authentication — no jose dependency
- **Production secret guard**: `JWT_SECRET` must be set in non-dev environments; falls
  back to a dev-only default that raises `RuntimeError` in production
- **Timing-safe authentication**: `authenticate()` performs a dummy hash check on missing
  users to prevent timing-based enumeration

### Role hierarchy

Three roles with cascading permissions:
- **admin** (level 3): implicit access to all projects and all operations
- **researcher** (level 2): create/edit within assigned projects
- **reviewer** (level 1): read-only + review actions within assigned projects

`role_at_least(user_role, required_role)` checks hierarchy level.

### Project-level access control

- `ProjectMembershipRow` links users to projects with a project-specific role
- `check_project_access()` verifies membership + role hierarchy
- Admins bypass membership checks entirely

### Data isolation

- `project_guard.py` provides `guarded_get()` and `guarded_list()` that enforce:
  1. User has project membership with sufficient role
  2. Artifact belongs to the requested project (ownership verification)
- `CrossProjectAccessError` redacts the actual project ID from user-facing messages
  to prevent ownership information leakage
- Path traversal and null-byte injection in project/artifact IDs are blocked by
  the membership check (no matching membership exists for malformed IDs)

### Audit logging

- `audit_log()` records security-sensitive actions (login, access denied, permission changes)
- Separate from `EventLogRow` (operational events) to maintain a clean security audit trail

## Alternatives Considered

| Alternative | Pros | Cons | Why not chosen |
|------------|------|------|----------------|
| OAuth2 / OIDC (Auth0, Cognito) | Industry standard, SSO | External dependency, complexity | MVP doesn't need SSO |
| bcrypt | Widely used | Requires C extension (build issues on Windows) | PBKDF2 is stdlib, same security |
| PyJWT / python-jose | Feature-rich | Extra dependency | HMAC-SHA256 JWT is ~30 lines |
| Row-level security (PostgreSQL) | DB-enforced | SQLite incompatible, complex | Application-level guards are portable |

## Consequences

- All API endpoints must verify JWT tokens and check project access
- Adding a new role requires updating `ROLE_HIERARCHY` and testing hierarchy logic
- Project deletion cascades to all membership and artifact records
- Audit log grows indefinitely — future work should add retention policies

## References

- `packages/shared/auth.py` — JWT, passwords, roles, membership, audit
- `packages/shared/project_guard.py` — data isolation guards
- `packages/shared/db/models.py` — UserRow, ProjectMembershipRow, AuditLogRow
