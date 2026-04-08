"""Tests for P13-05: Auth seeding, login gate, and user identity.

AC-1: Login endpoint works with seeded credentials.
AC-2: Protected routes reject unauthenticated requests.
AC-3: Seed script creates default accounts.
AC-4: Frontend auth components exist.
"""

from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from packages.shared.auth import (
    authenticate,
    create_token,
    create_user,
    decode_token,
    add_project_member,
)
from packages.shared.db.models import Base, UserRow
from packages.shared.db import repository as repo
from apps.api.auth_deps import get_current_user


# ---------------------------------------------------------------------------
# Test DB + app with override
# ---------------------------------------------------------------------------

@pytest.fixture
def test_app():
    """Create a test app with an in-memory DB override."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_url = f"sqlite:///{tmp.name}"

    test_engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(bind=test_engine)

    # Seed a user
    db = TestSession()
    alice = create_user(db, "alice@egg.local", "Alice", "pass123", "researcher")
    repo.create_project(db, "proj-alice", "Alice Project", "segmentation")
    add_project_member(db, alice.id, "proj-alice", "researcher")
    db.commit()
    alice_id = alice.id
    db.close()

    # Patch the engine module to use our test DB
    import packages.shared.db.engine as engine_mod
    orig_session = engine_mod.SessionLocal
    engine_mod.SessionLocal = TestSession

    from apps.api.main import app
    client = TestClient(app)

    yield client, alice_id

    engine_mod.SessionLocal = orig_session
    test_engine.dispose()
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# AC-1: Login endpoint
# ---------------------------------------------------------------------------

class TestLoginEndpoint:
    def test_login_rejects_bad_credentials(self, test_app):
        client, _ = test_app
        resp = client.post("/api/v1/auth/login", json={"email": "bad@bad.com", "password": "wrong"})
        assert resp.status_code == 401

    def test_login_success_returns_token(self, test_app):
        client, _ = test_app
        resp = client.post("/api/v1/auth/login", json={"email": "alice@egg.local", "password": "pass123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["email"] == "alice@egg.local"
        assert data["role"] == "researcher"
        assert "user_id" in data

    def test_login_token_is_valid_jwt(self, test_app):
        client, _ = test_app
        resp = client.post("/api/v1/auth/login", json={"email": "alice@egg.local", "password": "pass123"})
        token = resp.json()["token"]
        payload = decode_token(token)
        assert payload.email == "alice@egg.local"
        assert payload.role == "researcher"


# ---------------------------------------------------------------------------
# AC-2: Auth middleware
# ---------------------------------------------------------------------------

class TestAuthMiddleware:
    def test_projects_rejects_unauthenticated(self, test_app):
        client, _ = test_app
        resp = client.get("/api/v1/projects/")
        assert resp.status_code == 401

    def test_projects_rejects_bad_token(self, test_app):
        client, _ = test_app
        resp = client.get("/api/v1/projects/", headers={"Authorization": "Bearer garbage"})
        assert resp.status_code == 401

    def test_projects_accepts_valid_token(self, test_app):
        client, alice_id = test_app
        headers = {"Authorization": f"Bearer {create_token(alice_id, 'alice@egg.local', 'researcher')}"}
        resp = client.get("/api/v1/projects/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "projects" in data

    def test_user_sees_own_projects(self, test_app):
        client, alice_id = test_app
        headers = {"Authorization": f"Bearer {create_token(alice_id, 'alice@egg.local', 'researcher')}"}
        resp = client.get("/api/v1/projects/", headers=headers)
        projects = resp.json()["projects"]
        assert len(projects) == 1
        assert projects[0]["name"] == "Alice Project"

    def test_health_does_not_require_auth(self, test_app):
        client, _ = test_app
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_ops_does_not_require_auth(self, test_app):
        client, _ = test_app
        resp = client.get("/ops/metrics")
        assert resp.status_code == 200

    def test_create_project_requires_auth(self, test_app):
        client, _ = test_app
        resp = client.post("/api/v1/projects/", json={"name": "Test", "methodology": "seg"})
        assert resp.status_code == 401

    def test_create_project_with_auth(self, test_app):
        client, alice_id = test_app
        headers = {"Authorization": f"Bearer {create_token(alice_id, 'alice@egg.local', 'researcher')}"}
        resp = client.post("/api/v1/projects/", json={"name": "New Project", "methodology": "drivers"}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "New Project"
        assert "id" in data


# ---------------------------------------------------------------------------
# AC-3: Seed script
# ---------------------------------------------------------------------------

class TestSeedScript:
    def test_seed_script_exists(self):
        from pathlib import Path
        assert (Path(__file__).resolve().parents[2] / "scripts" / "seed_users.py").is_file()

    def test_seed_defines_default_users(self):
        from scripts.seed_users import DEFAULT_USERS
        emails = [u["email"] for u in DEFAULT_USERS]
        assert "admin@egg.local" in emails
        assert "researcher@egg.local" in emails
        assert "reviewer@egg.local" in emails

    def test_seed_has_three_roles(self):
        from scripts.seed_users import DEFAULT_USERS
        roles = {u["role"] for u in DEFAULT_USERS}
        assert roles == {"admin", "researcher", "reviewer"}


# ---------------------------------------------------------------------------
# AC-4: Frontend auth components
# ---------------------------------------------------------------------------

class TestFrontendAuth:
    def test_auth_guard_exists(self):
        from pathlib import Path
        assert (Path(__file__).resolve().parents[2] / "apps" / "web" / "frontend" / "src" / "components" / "AuthGuard.tsx").is_file()

    def test_login_page_exists(self):
        from pathlib import Path
        assert (Path(__file__).resolve().parents[2] / "apps" / "web" / "frontend" / "src" / "pages" / "LoginPage.tsx").is_file()

    def test_auth_module_exists(self):
        from pathlib import Path
        assert (Path(__file__).resolve().parents[2] / "apps" / "web" / "frontend" / "src" / "api" / "auth.ts").is_file()

    def test_auth_deps_module_exists(self):
        from apps.api.auth_deps import get_current_user, CurrentUser
        assert callable(get_current_user)
