"""Tests for P09-02: Authentication, RBAC, and project-level authorization.

AC-1: Roles include admin, researcher, reviewer.
AC-2: Every project artifact endpoint enforces project membership + role checks.
AC-3: Audit logs capture actor, action, project, artifact refs.
"""

from __future__ import annotations

import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from packages.shared.db.models import Base, ProjectRow
from packages.shared.db import repository as repo
from packages.shared.auth import (
    Role,
    TokenPayload,
    add_project_member,
    audit_log,
    authenticate,
    check_project_access,
    create_token,
    create_user,
    decode_token,
    get_user,
    get_user_projects,
    hash_password,
    list_audit_log,
    role_at_least,
    verify_password,
)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _commit(db: Session):
    db.commit()


# ---------------------------------------------------------------------------
# AC-1: Roles
# ---------------------------------------------------------------------------

class TestRoles:
    def test_role_enum_values(self):
        assert Role.ADMIN.value == "admin"
        assert Role.RESEARCHER.value == "researcher"
        assert Role.REVIEWER.value == "reviewer"

    def test_admin_outranks_all(self):
        assert role_at_least("admin", "admin")
        assert role_at_least("admin", "researcher")
        assert role_at_least("admin", "reviewer")

    def test_researcher_outranks_reviewer(self):
        assert role_at_least("researcher", "reviewer")
        assert role_at_least("researcher", "researcher")
        assert not role_at_least("researcher", "admin")

    def test_reviewer_is_lowest(self):
        assert role_at_least("reviewer", "reviewer")
        assert not role_at_least("reviewer", "researcher")
        assert not role_at_least("reviewer", "admin")


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

class TestPasswordHashing:
    def test_hash_and_verify(self):
        hashed = hash_password("secret123")
        assert verify_password("secret123", hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("secret123")
        assert not verify_password("wrong", hashed)

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # different salts

    def test_corrupt_hash_returns_false(self):
        assert not verify_password("anything", "not-a-valid-hash")


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

class TestJWT:
    def test_create_and_decode(self):
        token = create_token("user-001", "test@example.com", "researcher")
        payload = decode_token(token)
        assert payload.sub == "user-001"
        assert payload.email == "test@example.com"
        assert payload.role == "researcher"

    def test_expired_token_fails(self):
        import packages.shared.auth as auth_mod
        original = auth_mod.JWT_EXPIRY_SECONDS
        auth_mod.JWT_EXPIRY_SECONDS = -1  # already expired
        token = create_token("user-001", "test@example.com", "admin")
        auth_mod.JWT_EXPIRY_SECONDS = original
        with pytest.raises(ValueError, match="expired"):
            decode_token(token)

    def test_tampered_token_fails(self):
        token = create_token("user-001", "test@example.com", "admin")
        parts = token.split(".")
        tampered = parts[0] + "." + parts[1] + ".tampered_signature"
        with pytest.raises(ValueError, match="signature"):
            decode_token(tampered)

    def test_invalid_format_too_many_parts(self):
        with pytest.raises(ValueError, match="format"):
            decode_token("not.a.valid.token.with.too.many.parts")

    def test_invalid_format_too_few_parts(self):
        with pytest.raises(ValueError, match="format"):
            decode_token("only.two")


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

class TestUserManagement:
    def test_create_user(self, db: Session):
        user = create_user(db, "alice@example.com", "Alice", "pass123", "researcher")
        _commit(db)
        assert user.id.startswith("user-")
        assert user.email == "alice@example.com"
        assert user.role == "researcher"

    def test_duplicate_email_raises(self, db: Session):
        create_user(db, "alice@example.com", "Alice", "pass123")
        _commit(db)
        with pytest.raises(ValueError, match="already exists"):
            create_user(db, "alice@example.com", "Alice 2", "pass456")

    def test_authenticate_success(self, db: Session):
        create_user(db, "alice@example.com", "Alice", "pass123")
        _commit(db)
        user = authenticate(db, "alice@example.com", "pass123")
        assert user is not None
        assert user.email == "alice@example.com"

    def test_authenticate_wrong_password(self, db: Session):
        create_user(db, "alice@example.com", "Alice", "pass123")
        _commit(db)
        assert authenticate(db, "alice@example.com", "wrong") is None

    def test_authenticate_nonexistent_user(self, db: Session):
        assert authenticate(db, "nobody@example.com", "pass") is None

    def test_authenticate_inactive_user_rejected(self, db: Session):
        user = create_user(db, "inactive@example.com", "Inactive", "pass123")
        user.is_active = False
        _commit(db)
        assert authenticate(db, "inactive@example.com", "pass123") is None

    def test_get_user(self, db: Session):
        user = create_user(db, "alice@example.com", "Alice", "pass123")
        _commit(db)
        retrieved = get_user(db, user.id)
        assert retrieved is not None


# ---------------------------------------------------------------------------
# AC-2: Project membership + role checks
# ---------------------------------------------------------------------------

class TestProjectAccess:
    def _setup(self, db: Session):
        repo.create_project(db, "proj-001", "Test", "segmentation")
        repo.create_project(db, "proj-002", "Other", "drivers")
        self.admin = create_user(db, "admin@test.com", "Admin", "pass", "admin")
        self.researcher = create_user(db, "researcher@test.com", "Researcher", "pass", "researcher")
        self.reviewer = create_user(db, "reviewer@test.com", "Reviewer", "pass", "reviewer")
        add_project_member(db, self.researcher.id, "proj-001", "researcher")
        add_project_member(db, self.reviewer.id, "proj-001", "reviewer")
        _commit(db)

    def test_admin_has_access_everywhere(self, db: Session):
        self._setup(db)
        assert check_project_access(db, self.admin.id, "proj-001") is True
        assert check_project_access(db, self.admin.id, "proj-002") is True

    def test_researcher_access_own_project(self, db: Session):
        self._setup(db)
        assert check_project_access(db, self.researcher.id, "proj-001") is True

    def test_researcher_no_access_other_project(self, db: Session):
        self._setup(db)
        assert check_project_access(db, self.researcher.id, "proj-002") is False

    def test_reviewer_read_access(self, db: Session):
        self._setup(db)
        assert check_project_access(db, self.reviewer.id, "proj-001", "reviewer") is True

    def test_reviewer_cannot_write(self, db: Session):
        self._setup(db)
        assert check_project_access(db, self.reviewer.id, "proj-001", "researcher") is False

    def test_nonexistent_user_denied(self, db: Session):
        self._setup(db)
        assert check_project_access(db, "fake-user", "proj-001") is False

    def test_get_user_projects(self, db: Session):
        self._setup(db)
        # Admin sees all
        admin_projects = get_user_projects(db, self.admin.id)
        assert len(admin_projects) >= 2
        # Researcher sees only assigned
        researcher_projects = get_user_projects(db, self.researcher.id)
        assert researcher_projects == ["proj-001"]

    def test_update_membership_role(self, db: Session):
        self._setup(db)
        add_project_member(db, self.reviewer.id, "proj-001", "researcher")  # upgrade
        _commit(db)
        assert check_project_access(db, self.reviewer.id, "proj-001", "researcher") is True


# ---------------------------------------------------------------------------
# AC-3: Audit logging
# ---------------------------------------------------------------------------

class TestAuditLog:
    def test_log_action(self, db: Session):
        entry = audit_log(
            db, actor_id="user-001", actor_email="alice@test.com",
            action="login", detail="Successful login",
        )
        _commit(db)
        assert entry.id is not None
        assert entry.action == "login"

    def test_log_with_project_and_artifact(self, db: Session):
        audit_log(
            db, actor_id="user-001", actor_email="alice@test.com",
            action="delete_questionnaire", project_id="proj-001",
            artifact_type="questionnaire", artifact_id="qre-001",
            detail="Deleted version 3",
        )
        _commit(db)
        logs = list_audit_log(db, project_id="proj-001")
        assert len(logs) == 1
        assert logs[0].artifact_type == "questionnaire"
        assert logs[0].artifact_id == "qre-001"

    def test_filter_by_actor(self, db: Session):
        audit_log(db, "user-001", "alice@test.com", "login")
        audit_log(db, "user-002", "bob@test.com", "login")
        _commit(db)
        logs = list_audit_log(db, actor_id="user-001")
        assert len(logs) == 1

    def test_filter_by_action(self, db: Session):
        audit_log(db, "user-001", "alice@test.com", "login")
        audit_log(db, "user-001", "alice@test.com", "create_project")
        _commit(db)
        logs = list_audit_log(db, action="create_project")
        assert len(logs) == 1

    def test_ip_address_captured(self, db: Session):
        audit_log(
            db, "user-001", "alice@test.com", "login",
            ip_address="192.168.1.100",
        )
        _commit(db)
        logs = list_audit_log(db, actor_id="user-001")
        assert logs[0].ip_address == "192.168.1.100"
