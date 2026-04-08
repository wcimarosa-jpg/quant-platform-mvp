"""Tests for resource-level authorization on briefs/drafts/tables routes.

Addresses Codex review B2: even with auth, any user can guess resource
IDs from other projects. These tests verify that one user cannot access
another user's briefs/drafts/runs.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from apps.api.auth_deps import get_current_user
from apps.api.main import app
from apps.api.resource_auth import reset_all_ownership
from packages.shared.auth import TokenPayload


def _user(sub: str, role: str = "researcher") -> TokenPayload:
    return TokenPayload(
        sub=sub,
        email=f"{sub}@egg.local",
        role=role,
        exp=9999999999,
        iat=0,
    )


@pytest.fixture(autouse=True)
def reset_resources():
    """Reset ownership and clear in-memory stores between tests."""
    reset_all_ownership()
    from apps.api.routes.briefs import _briefs
    from apps.api.routes.drafts import _store
    from apps.api.routes.tables import _runs, _qa_reports, _copilot_sessions
    _briefs.clear()
    _store._drafts.clear() if hasattr(_store, "_drafts") else None
    _runs.clear()
    _qa_reports.clear()
    _copilot_sessions.clear()
    yield
    reset_all_ownership()


@pytest.fixture
def client_as_user():
    """Returns a function that creates a TestClient impersonating a given user."""
    def _make(sub: str, role: str = "researcher") -> TestClient:
        app.dependency_overrides[get_current_user] = lambda: _user(sub, role)
        return TestClient(app)
    yield _make
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Briefs cross-user access
# ---------------------------------------------------------------------------

class TestBriefsAuthorization:
    def test_other_user_cannot_read_brief(self, client_as_user):
        # Alice uploads a brief
        alice_client = client_as_user("alice")
        files = {"file": ("brief.md", io.BytesIO(b"# Brief\nObjectives: test"), "text/markdown")}
        resp = alice_client.post("/api/v1/briefs/upload?project_id=proj-alice", files=files)
        assert resp.status_code == 200
        brief_id = resp.json()["brief_id"]

        # Bob tries to read it
        bob_client = client_as_user("bob")
        resp = bob_client.get(f"/api/v1/briefs/{brief_id}")
        assert resp.status_code == 403

    def test_other_user_cannot_update_brief(self, client_as_user):
        alice_client = client_as_user("alice")
        files = {"file": ("brief.md", io.BytesIO(b"# Brief\nObjectives: test"), "text/markdown")}
        resp = alice_client.post("/api/v1/briefs/upload?project_id=proj-alice", files=files)
        brief_id = resp.json()["brief_id"]

        bob_client = client_as_user("bob")
        resp = bob_client.patch(f"/api/v1/briefs/{brief_id}", json={"objectives": "hijacked"})
        assert resp.status_code == 403

    def test_owner_can_read_own_brief(self, client_as_user):
        alice_client = client_as_user("alice")
        files = {"file": ("brief.md", io.BytesIO(b"# Brief\nObjectives: test"), "text/markdown")}
        resp = alice_client.post("/api/v1/briefs/upload?project_id=proj-alice", files=files)
        brief_id = resp.json()["brief_id"]

        resp = alice_client.get(f"/api/v1/briefs/{brief_id}")
        assert resp.status_code == 200

    def test_admin_can_read_any_brief(self, client_as_user):
        alice_client = client_as_user("alice")
        files = {"file": ("brief.md", io.BytesIO(b"# Brief\nObjectives: test"), "text/markdown")}
        resp = alice_client.post("/api/v1/briefs/upload?project_id=proj-alice", files=files)
        brief_id = resp.json()["brief_id"]

        admin_client = client_as_user("admin", role="admin")
        resp = admin_client.get(f"/api/v1/briefs/{brief_id}")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Drafts cross-user access
# ---------------------------------------------------------------------------

class TestDraftsAuthorization:
    def test_other_user_cannot_read_draft(self, client_as_user):
        alice_client = client_as_user("alice")
        resp = alice_client.post("/api/v1/drafts/", json={"project_id": "proj-alice", "methodology": "segmentation"})
        assert resp.status_code == 200
        draft_id = resp.json()["draft_id"]

        bob_client = client_as_user("bob")
        resp = bob_client.get(f"/api/v1/drafts/{draft_id}")
        assert resp.status_code == 403

    def test_other_user_cannot_update_methodology(self, client_as_user):
        alice_client = client_as_user("alice")
        resp = alice_client.post("/api/v1/drafts/", json={"project_id": "proj-alice", "methodology": "segmentation"})
        draft_id = resp.json()["draft_id"]

        bob_client = client_as_user("bob")
        resp = bob_client.patch(f"/api/v1/drafts/{draft_id}/methodology", json={"methodology": "drivers"})
        assert resp.status_code == 403

    def test_other_user_cannot_update_sections(self, client_as_user):
        alice_client = client_as_user("alice")
        resp = alice_client.post("/api/v1/drafts/", json={"project_id": "proj-alice", "methodology": "segmentation"})
        draft_id = resp.json()["draft_id"]

        bob_client = client_as_user("bob")
        resp = bob_client.patch(f"/api/v1/drafts/{draft_id}/sections", json={"selected_sections": []})
        assert resp.status_code == 403

    def test_other_user_cannot_get_generation_config(self, client_as_user):
        alice_client = client_as_user("alice")
        resp = alice_client.post("/api/v1/drafts/", json={"project_id": "proj-alice", "methodology": "segmentation"})
        draft_id = resp.json()["draft_id"]

        bob_client = client_as_user("bob")
        resp = bob_client.get(f"/api/v1/drafts/{draft_id}/generation-config")
        assert resp.status_code == 403

    def test_owner_can_read_own_draft(self, client_as_user):
        alice_client = client_as_user("alice")
        resp = alice_client.post("/api/v1/drafts/", json={"project_id": "proj-alice", "methodology": "segmentation"})
        draft_id = resp.json()["draft_id"]

        resp = alice_client.get(f"/api/v1/drafts/{draft_id}")
        assert resp.status_code == 200

    def test_admin_can_read_any_draft(self, client_as_user):
        alice_client = client_as_user("alice")
        resp = alice_client.post("/api/v1/drafts/", json={"project_id": "proj-alice", "methodology": "segmentation"})
        draft_id = resp.json()["draft_id"]

        admin_client = client_as_user("admin", role="admin")
        resp = admin_client.get(f"/api/v1/drafts/{draft_id}")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tables cross-user access
# ---------------------------------------------------------------------------

class TestTablesAuthorization:
    def _generate_payload(self, project_id: str = "proj-alice"):
        return {
            "project_id": project_id,
            "mapping_id": "map-1",
            "variables": [
                {
                    "var_name": "Q1",
                    "var_label": "Question 1",
                    "var_type": "single",
                    "value_labels": {"1": "A", "2": "B", "3": "C"},
                },
            ],
            "data_rows": [{"Q1": 1}, {"Q1": 2}, {"Q1": 1}, {"Q1": 3}],
        }

    def test_other_user_cannot_qa_run(self, client_as_user):
        alice_client = client_as_user("alice")
        resp = alice_client.post("/api/v1/tables/generate", json=self._generate_payload())
        assert resp.status_code == 200
        run_id = resp.json()["run_id"]

        bob_client = client_as_user("bob")
        resp = bob_client.post(f"/api/v1/tables/{run_id}/qa")
        assert resp.status_code == 403

    def test_other_user_cannot_qa_copilot(self, client_as_user):
        alice_client = client_as_user("alice")
        resp = alice_client.post("/api/v1/tables/generate", json=self._generate_payload())
        run_id = resp.json()["run_id"]
        alice_client.post(f"/api/v1/tables/{run_id}/qa")  # generate the QA report

        bob_client = client_as_user("bob")
        resp = bob_client.post(f"/api/v1/tables/{run_id}/qa-copilot")
        assert resp.status_code == 403

    def test_owner_can_qa_own_run(self, client_as_user):
        alice_client = client_as_user("alice")
        resp = alice_client.post("/api/v1/tables/generate", json=self._generate_payload())
        run_id = resp.json()["run_id"]

        resp = alice_client.post(f"/api/v1/tables/{run_id}/qa")
        assert resp.status_code == 200

    def test_admin_can_qa_any_run(self, client_as_user):
        alice_client = client_as_user("alice")
        resp = alice_client.post("/api/v1/tables/generate", json=self._generate_payload())
        run_id = resp.json()["run_id"]

        admin_client = client_as_user("admin", role="admin")
        resp = admin_client.post(f"/api/v1/tables/{run_id}/qa")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# resource_auth helper unit tests
# ---------------------------------------------------------------------------

class TestResourceAuthHelpers:
    def test_record_and_get_ownership(self):
        from apps.api.resource_auth import record_ownership, get_ownership
        record_ownership("test-1", owner_id="alice", project_id="proj-1")
        meta = get_ownership("test-1")
        assert meta == {"owner_id": "alice", "project_id": "proj-1"}

    def test_require_owner_passes_for_owner(self):
        from apps.api.resource_auth import record_ownership, require_owner
        record_ownership("test-2", owner_id="alice", project_id="proj-1")
        require_owner("test-2", _user("alice"))  # should not raise

    def test_require_owner_fails_for_other_user(self):
        from apps.api.resource_auth import record_ownership, require_owner
        from fastapi import HTTPException
        record_ownership("test-3", owner_id="alice", project_id="proj-1")
        with pytest.raises(HTTPException) as exc:
            require_owner("test-3", _user("bob"))
        assert exc.value.status_code == 403

    def test_require_owner_admin_bypass(self):
        from apps.api.resource_auth import record_ownership, require_owner
        record_ownership("test-4", owner_id="alice", project_id="proj-1")
        require_owner("test-4", _user("anyone", role="admin"))  # should not raise

    def test_require_owner_unknown_resource_404(self):
        from apps.api.resource_auth import require_owner
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            require_owner("nonexistent", _user("alice"))
        assert exc.value.status_code == 404

    def test_clear_ownership(self):
        from apps.api.resource_auth import record_ownership, get_ownership, clear_ownership
        record_ownership("test-5", owner_id="alice")
        clear_ownership("test-5")
        assert get_ownership("test-5") is None
