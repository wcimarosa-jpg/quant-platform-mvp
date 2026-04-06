"""Tests for P09-05: Project data isolation and storage boundaries.

AC-1: Service-layer checks reject cross-project access.
AC-2: All stored artifacts tagged with project ownership.
AC-3: Security tests: traversal + cross-project attack scenarios.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from packages.shared.db.models import (
    AnalysisRunRow,
    Base,
    BriefRow,
    MappingRow,
    ProjectRow,
    QuestionnaireRow,
)
from packages.shared.db import repository as repo
from packages.shared.auth import add_project_member, create_user
from packages.shared.project_guard import (
    CrossProjectAccessError,
    ProjectAccessDenied,
    guarded_get,
    guarded_list,
    tag_artifact_ownership,
    verify_artifact_ownership,
)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _commit(db):
    db.commit()


def _setup(db: Session):
    """Create two projects, two users, with isolated access."""
    repo.create_project(db, "proj-alpha", "Alpha Project", "segmentation")
    repo.create_project(db, "proj-beta", "Beta Project", "drivers")

    # Alice: researcher on Alpha only
    alice = create_user(db, "alice@test.com", "Alice", "pass", "researcher")
    add_project_member(db, alice.id, "proj-alpha", "researcher")

    # Bob: researcher on Beta only
    bob = create_user(db, "bob@test.com", "Bob", "pass", "researcher")
    add_project_member(db, bob.id, "proj-beta", "researcher")

    # Admin: access everywhere
    admin = create_user(db, "admin@test.com", "Admin", "pass", "admin")

    # Artifacts in each project
    repo.save_brief(db, BriefRow(id="brief-a1", project_id="proj-alpha", objectives="Alpha brief"))
    repo.save_brief(db, BriefRow(id="brief-b1", project_id="proj-beta", objectives="Beta brief"))
    repo.save_questionnaire(db, QuestionnaireRow(
        id="qre-a1", project_id="proj-alpha", methodology="seg", version=1, sections_json=[],
    ))
    repo.save_mapping(db, MappingRow(
        id="map-b1", project_id="proj-beta", version=1, mappings_json=[],
    ))
    repo.save_run(db, AnalysisRunRow(
        id="run-a1", project_id="proj-alpha", analysis_type="drivers", status="completed",
    ))

    _commit(db)
    return {"alice": alice, "bob": bob, "admin": admin}


# ---------------------------------------------------------------------------
# AC-1: Cross-project access rejected
# ---------------------------------------------------------------------------

class TestCrossProjectRejection:
    def test_alice_cannot_access_beta_brief(self, db: Session):
        users = _setup(db)
        with pytest.raises(ProjectAccessDenied):
            guarded_get(db, users["alice"].id, "proj-beta", "brief", "brief-b1")

    def test_bob_cannot_access_alpha_brief(self, db: Session):
        users = _setup(db)
        with pytest.raises(ProjectAccessDenied):
            guarded_get(db, users["bob"].id, "proj-alpha", "brief", "brief-a1")

    def test_alice_can_access_own_project_brief(self, db: Session):
        users = _setup(db)
        brief = guarded_get(db, users["alice"].id, "proj-alpha", "brief", "brief-a1")
        assert brief.id == "brief-a1"

    def test_admin_can_access_any_project(self, db: Session):
        users = _setup(db)
        brief = guarded_get(db, users["admin"].id, "proj-beta", "brief", "brief-b1")
        assert brief.id == "brief-b1"

    def test_artifact_from_wrong_project_blocked(self, db: Session):
        """Even if user has access to the project, artifact must belong to it."""
        users = _setup(db)
        # Admin accesses proj-alpha but asks for proj-beta's brief
        with pytest.raises(CrossProjectAccessError):
            guarded_get(db, users["admin"].id, "proj-alpha", "brief", "brief-b1")

    def test_nonexistent_user_denied(self, db: Session):
        _setup(db)
        with pytest.raises(ProjectAccessDenied):
            guarded_get(db, "fake-user", "proj-alpha", "brief", "brief-a1")

    def test_nonexistent_artifact_raises(self, db: Session):
        users = _setup(db)
        with pytest.raises(ValueError, match="not found"):
            guarded_get(db, users["alice"].id, "proj-alpha", "brief", "nonexistent")


# ---------------------------------------------------------------------------
# AC-1: Guarded list
# ---------------------------------------------------------------------------

class TestGuardedList:
    def test_list_only_own_project(self, db: Session):
        users = _setup(db)
        briefs = guarded_list(db, users["alice"].id, "proj-alpha", "brief")
        assert len(briefs) == 1
        assert briefs[0].id == "brief-a1"

    def test_list_blocked_for_non_member(self, db: Session):
        users = _setup(db)
        with pytest.raises(ProjectAccessDenied):
            guarded_list(db, users["alice"].id, "proj-beta", "brief")

    def test_admin_list_any_project(self, db: Session):
        users = _setup(db)
        briefs = guarded_list(db, users["admin"].id, "proj-beta", "brief")
        assert len(briefs) == 1

    def test_list_all_artifact_types(self, db: Session):
        users = _setup(db)
        for atype, expected in [("brief", 1), ("questionnaire", 1), ("run", 1)]:
            items = guarded_list(db, users["alice"].id, "proj-alpha", atype)
            assert len(items) == expected, f"{atype}: expected {expected}, got {len(items)}"


# ---------------------------------------------------------------------------
# AC-2: Ownership tagging
# ---------------------------------------------------------------------------

class TestOwnershipTagging:
    def test_tag_new_artifact(self, db: Session):
        _setup(db)
        brief = BriefRow(id="brief-new", objectives="New")
        tag_artifact_ownership(brief, "proj-alpha")
        assert brief.project_id == "proj-alpha"

    def test_tag_matching_project_ok(self, db: Session):
        _setup(db)
        brief = BriefRow(id="brief-new", project_id="proj-alpha", objectives="New")
        tag_artifact_ownership(brief, "proj-alpha")  # should not raise
        assert brief.project_id == "proj-alpha"

    def test_retag_different_project_raises(self, db: Session):
        _setup(db)
        brief = BriefRow(id="brief-new", project_id="proj-alpha", objectives="New")
        with pytest.raises(ValueError, match="Cannot re-tag"):
            tag_artifact_ownership(brief, "proj-beta")

    def test_verify_ownership_succeeds(self, db: Session):
        _setup(db)
        entity = verify_artifact_ownership(db, "brief", "brief-a1", "proj-alpha")
        assert entity.project_id == "proj-alpha"

    def test_verify_ownership_wrong_project(self, db: Session):
        _setup(db)
        with pytest.raises(CrossProjectAccessError) as exc_info:
            verify_artifact_ownership(db, "brief", "brief-a1", "proj-beta")
        assert exc_info.value.actual_project == "proj-alpha"
        assert exc_info.value.expected_project == "proj-beta"


# ---------------------------------------------------------------------------
# AC-3: Security attack scenarios
# ---------------------------------------------------------------------------

class TestSecurityAttacks:
    def test_cross_project_brief_access_via_id_guessing(self, db: Session):
        """Attacker knows brief-b1 ID, tries to access from proj-alpha context."""
        users = _setup(db)
        with pytest.raises(CrossProjectAccessError):
            verify_artifact_ownership(db, "brief", "brief-b1", "proj-alpha")

    def test_cross_project_questionnaire_access(self, db: Session):
        users = _setup(db)
        with pytest.raises(CrossProjectAccessError):
            verify_artifact_ownership(db, "questionnaire", "qre-a1", "proj-beta")

    def test_cross_project_mapping_access(self, db: Session):
        users = _setup(db)
        with pytest.raises(CrossProjectAccessError):
            verify_artifact_ownership(db, "mapping", "map-b1", "proj-alpha")

    def test_cross_project_run_access(self, db: Session):
        users = _setup(db)
        with pytest.raises(CrossProjectAccessError):
            verify_artifact_ownership(db, "run", "run-a1", "proj-beta")

    def test_escalation_via_role_downgrade_blocked(self, db: Session):
        """Reviewer cannot write even with guarded_get."""
        users = _setup(db)
        # Add Alice as reviewer on Beta (read-only)
        add_project_member(db, users["alice"].id, "proj-beta", "reviewer")
        _commit(db)
        # Read access works
        brief = guarded_get(db, users["alice"].id, "proj-beta", "brief", "brief-b1", required_role="reviewer")
        assert brief is not None
        # Write access denied
        with pytest.raises(ProjectAccessDenied):
            guarded_get(db, users["alice"].id, "proj-beta", "brief", "brief-b1", required_role="researcher")

    def test_unknown_artifact_type_rejected(self, db: Session):
        users = _setup(db)
        with pytest.raises(ValueError, match="Unknown artifact"):
            guarded_get(db, users["alice"].id, "proj-alpha", "secret_type", "x")

    def test_empty_project_returns_empty_list(self, db: Session):
        users = _setup(db)
        # proj-alpha has no mappings
        mappings = guarded_list(db, users["alice"].id, "proj-alpha", "mapping")
        assert mappings == []

    # -- Path traversal attack scenarios --

    def test_traversal_project_id_denied(self, db: Session):
        """Attacker uses '../proj-beta' as project_id to escape context."""
        users = _setup(db)
        with pytest.raises(ProjectAccessDenied):
            guarded_get(db, users["alice"].id, "../proj-beta", "brief", "brief-b1")

    def test_traversal_artifact_id_not_found(self, db: Session):
        """Attacker uses path traversal in artifact_id."""
        users = _setup(db)
        with pytest.raises(ValueError, match="not found"):
            guarded_get(db, users["alice"].id, "proj-alpha", "brief", "../../etc/passwd")

    def test_traversal_project_id_list_denied(self, db: Session):
        """Attacker uses traversal project_id in list endpoint."""
        users = _setup(db)
        with pytest.raises(ProjectAccessDenied):
            guarded_list(db, users["alice"].id, "../proj-beta", "brief")

    def test_null_byte_project_id_denied(self, db: Session):
        """Attacker injects null byte in project_id."""
        users = _setup(db)
        with pytest.raises(ProjectAccessDenied):
            guarded_get(db, users["alice"].id, "proj-alpha\x00proj-beta", "brief", "brief-a1")

    # -- Limit validation --

    def test_guarded_list_limit_clamped_high(self, db: Session):
        """Limit above 500 is clamped to 500 (no crash)."""
        users = _setup(db)
        briefs = guarded_list(db, users["alice"].id, "proj-alpha", "brief", limit=99999)
        assert len(briefs) == 1  # only one brief exists

    def test_guarded_list_limit_clamped_zero(self, db: Session):
        """Limit of 0 is clamped to 1 (no empty-by-default)."""
        users = _setup(db)
        briefs = guarded_list(db, users["alice"].id, "proj-alpha", "brief", limit=0)
        assert len(briefs) == 1

    def test_guarded_list_limit_clamped_negative(self, db: Session):
        """Negative limit is clamped to 1."""
        users = _setup(db)
        briefs = guarded_list(db, users["alice"].id, "proj-alpha", "brief", limit=-10)
        assert len(briefs) == 1
