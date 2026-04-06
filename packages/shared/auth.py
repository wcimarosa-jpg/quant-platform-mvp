"""Authentication, RBAC, and project-level authorization.

Provides JWT token creation/validation, password hashing, role-based
access control, project membership checks, and security audit logging.

Roles: admin, researcher, reviewer
- admin: full access to all projects and settings
- researcher: create/edit within assigned projects
- reviewer: read-only + review actions within assigned projects
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from .db.models import AuditLogRow, ProjectMembershipRow, UserRow


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_SECRET = "dev-secret-change-in-production"
JWT_SECRET = os.getenv("JWT_SECRET", _DEFAULT_SECRET)
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_SECONDS = int(os.getenv("JWT_EXPIRY_SECONDS", "3600"))  # 1 hour

# Block default secret in non-dev environments
_ENV = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower()
if JWT_SECRET == _DEFAULT_SECRET and _ENV not in ("dev", "development", "test", "testing"):
    raise RuntimeError(
        "JWT_SECRET must be set in production. "
        "Set JWT_SECRET env var to a strong random string."
    )


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

class Role(str, Enum):
    ADMIN = "admin"
    RESEARCHER = "researcher"
    REVIEWER = "reviewer"


ROLE_HIERARCHY = {Role.ADMIN: 3, Role.RESEARCHER: 2, Role.REVIEWER: 1}


def role_at_least(user_role: str, required_role: str) -> bool:
    """Check if user_role meets or exceeds required_role in hierarchy."""
    user_level = ROLE_HIERARCHY.get(Role(user_role), 0)
    required_level = ROLE_HIERARCHY.get(Role(required_role), 99)
    return user_level >= required_level


# ---------------------------------------------------------------------------
# Password hashing (PBKDF2-SHA256 — no bcrypt dependency needed)
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return f"{salt.hex()}:{dk.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        salt_hex, dk_hex = hashed.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT (minimal, no jose dependency — HMAC-SHA256)
# ---------------------------------------------------------------------------

def _b64url(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    import base64
    padding = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * padding)


def create_token(user_id: str, email: str, role: str) -> str:
    """Create a JWT token."""
    header = _b64url(json.dumps({"alg": JWT_ALGORITHM, "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": int(time.time()) + JWT_EXPIRY_SECONDS,
        "iat": int(time.time()),
    }).encode())
    signature = _b64url(hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), "sha256").digest())
    return f"{header}.{payload}.{signature}"


class TokenPayload(BaseModel):
    sub: str         # user_id
    email: str
    role: str
    exp: int
    iat: int


def decode_token(token: str) -> TokenPayload:
    """Decode and verify a JWT token. Raises ValueError on invalid/expired."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format.")
    header, payload, signature = parts

    expected_sig = _b64url(hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), "sha256").digest())
    if not hmac.compare_digest(signature, expected_sig):
        raise ValueError("Invalid token signature.")

    data = json.loads(_b64url_decode(payload))
    if data.get("exp", 0) < time.time():
        raise ValueError("Token expired.")

    return TokenPayload(**data)


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

def create_user(
    db: Session, email: str, display_name: str, password: str, role: str = "researcher",
) -> UserRow:
    """Create a new user. Caller must commit."""
    if db.query(UserRow).filter(UserRow.email == email).first():
        raise ValueError(f"User with email {email!r} already exists.")
    user = UserRow(
        id=f"user-{uuid.uuid4().hex[:16]}",
        email=email,
        display_name=display_name,
        hashed_password=hash_password(password),
        role=role,
    )
    db.add(user)
    db.flush()
    return user


_DUMMY_HASH = hash_password("dummy-for-timing-safety")


def authenticate(db: Session, email: str, password: str) -> UserRow | None:
    """Verify credentials. Returns user or None.

    Performs a dummy hash check when user is not found to prevent
    timing-based user enumeration.
    """
    user = db.query(UserRow).filter(UserRow.email == email, UserRow.is_active == True).first()
    if not user:
        verify_password(password, _DUMMY_HASH)  # constant-time regardless of existence
        return None
    if verify_password(password, user.hashed_password):
        return user
    return None


def get_user(db: Session, user_id: str) -> UserRow | None:
    return db.query(UserRow).filter(UserRow.id == user_id).first()


# ---------------------------------------------------------------------------
# Project membership
# ---------------------------------------------------------------------------

def add_project_member(
    db: Session, user_id: str, project_id: str, role: str = "researcher",
) -> ProjectMembershipRow:
    """Add a user to a project. Caller must commit."""
    existing = (
        db.query(ProjectMembershipRow)
        .filter(ProjectMembershipRow.user_id == user_id, ProjectMembershipRow.project_id == project_id)
        .first()
    )
    if existing:
        existing.role = role
        db.flush()
        return existing
    membership = ProjectMembershipRow(user_id=user_id, project_id=project_id, role=role)
    db.add(membership)
    db.flush()
    return membership


def check_project_access(db: Session, user_id: str, project_id: str, required_role: str = "reviewer") -> bool:
    """Check if user has access to project with at least required_role.

    Admins have implicit access to all projects.
    """
    user = get_user(db, user_id)
    if not user:
        return False
    if user.role == Role.ADMIN.value:
        return True

    membership = (
        db.query(ProjectMembershipRow)
        .filter(ProjectMembershipRow.user_id == user_id, ProjectMembershipRow.project_id == project_id)
        .first()
    )
    if not membership:
        return False
    return role_at_least(membership.role, required_role)


def get_user_projects(db: Session, user_id: str) -> list[str]:
    """Return project IDs the user has access to."""
    user = get_user(db, user_id)
    if not user:
        return []
    if user.role == Role.ADMIN.value:
        from .db.models import ProjectRow
        return [p.id for p in db.query(ProjectRow).all()]
    memberships = db.query(ProjectMembershipRow).filter(ProjectMembershipRow.user_id == user_id).all()
    return [m.project_id for m in memberships]


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

def audit_log(
    db: Session,
    actor_id: str,
    actor_email: str,
    action: str,
    project_id: str | None = None,
    artifact_type: str | None = None,
    artifact_id: str | None = None,
    detail: str | None = None,
    ip_address: str | None = None,
) -> AuditLogRow:
    """Log a security-sensitive action. Caller must commit."""
    row = AuditLogRow(
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        project_id=project_id,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        detail=detail,
        ip_address=ip_address,
    )
    db.add(row)
    db.flush()
    return row


def list_audit_log(
    db: Session,
    actor_id: str | None = None,
    project_id: str | None = None,
    action: str | None = None,
    limit: int = 100,
) -> list[AuditLogRow]:
    q = db.query(AuditLogRow)
    if actor_id:
        q = q.filter(AuditLogRow.actor_id == actor_id)
    if project_id:
        q = q.filter(AuditLogRow.project_id == project_id)
    if action:
        q = q.filter(AuditLogRow.action == action)
    return q.order_by(AuditLogRow.created_at.desc()).limit(limit).all()
