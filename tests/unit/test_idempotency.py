"""Tests for P09-06: Idempotency keys and duplicate-run protection.

AC-1: Idempotency key generation is deterministic and collision-resistant.
AC-2: Duplicate job enqueue is rejected with DuplicateJobError.
AC-3: Duplicate analysis run creation returns existing run.
AC-4: Active-run detection prevents concurrent same-type runs.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from packages.shared.db.models import AnalysisRunRow, Base, ProjectRow
from packages.shared.db import repository as repo
from packages.shared.idempotency import (
    DuplicateRunError,
    check_duplicate_active_run,
    create_run_idempotent,
    generate_idempotency_key,
    get_run_by_idempotency_key,
    make_random_idempotency_key,
)
from packages.shared.job_queue import (
    DuplicateJobError,
    JobRow,
    enqueue_job,
    get_job_by_idempotency_key,
)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _setup(db: Session):
    repo.create_project(db, "proj-a", "Alpha", "segmentation")
    repo.create_project(db, "proj-b", "Beta", "drivers")
    db.commit()


# ---------------------------------------------------------------------------
# AC-1: Key generation
# ---------------------------------------------------------------------------

class TestKeyGeneration:
    def test_deterministic(self):
        k1 = generate_idempotency_key("proj-a", "drivers", params={"target": "Q1"})
        k2 = generate_idempotency_key("proj-a", "drivers", params={"target": "Q1"})
        assert k1 == k2

    def test_different_params_different_key(self):
        k1 = generate_idempotency_key("proj-a", "drivers", params={"target": "Q1"})
        k2 = generate_idempotency_key("proj-a", "drivers", params={"target": "Q2"})
        assert k1 != k2

    def test_different_project_different_key(self):
        k1 = generate_idempotency_key("proj-a", "drivers")
        k2 = generate_idempotency_key("proj-b", "drivers")
        assert k1 != k2

    def test_different_operation_different_key(self):
        k1 = generate_idempotency_key("proj-a", "drivers")
        k2 = generate_idempotency_key("proj-a", "segmentation")
        assert k1 != k2

    def test_nonce_changes_key(self):
        k1 = generate_idempotency_key("proj-a", "drivers")
        k2 = generate_idempotency_key("proj-a", "drivers", nonce="retry-1")
        assert k1 != k2

    def test_key_is_hex_string(self):
        k = generate_idempotency_key("proj-a", "drivers")
        assert len(k) == 64  # SHA-256 hex
        int(k, 16)  # should not raise

    def test_param_order_irrelevant(self):
        k1 = generate_idempotency_key("proj-a", "drivers", params={"a": 1, "b": 2})
        k2 = generate_idempotency_key("proj-a", "drivers", params={"b": 2, "a": 1})
        assert k1 == k2

    def test_random_key_unique(self):
        keys = {make_random_idempotency_key() for _ in range(100)}
        assert len(keys) == 100

    def test_complex_param_values_stable(self):
        """Nested dicts/lists produce stable keys regardless of insertion order."""
        k1 = generate_idempotency_key("p", "op", params={"cfg": {"z": 1, "a": 2}})
        k2 = generate_idempotency_key("p", "op", params={"cfg": {"a": 2, "z": 1}})
        assert k1 == k2

    def test_delimiter_in_value_no_collision(self):
        """Values containing null bytes or special chars don't cause collisions."""
        k1 = generate_idempotency_key("p", "op", params={"a": "x\x00b=y"})
        k2 = generate_idempotency_key("p", "op", params={"a": "x", "b": "y"})
        assert k1 != k2


# ---------------------------------------------------------------------------
# AC-2: Job queue idempotency
# ---------------------------------------------------------------------------

class TestJobIdempotency:
    def test_enqueue_with_idempotency_key(self, db: Session):
        _setup(db)
        job = enqueue_job(db, "drivers", {"x": 1}, project_id="proj-a", idempotency_key="key-1")
        assert job.idempotency_key == "key-1"

    def test_duplicate_key_raises(self, db: Session):
        _setup(db)
        job = enqueue_job(db, "drivers", {"x": 1}, project_id="proj-a", idempotency_key="key-dup")
        with pytest.raises(DuplicateJobError) as exc_info:
            enqueue_job(db, "drivers", {"x": 1}, project_id="proj-a", idempotency_key="key-dup")
        assert exc_info.value.job_id == job.id
        assert exc_info.value.status == "queued"

    def test_duplicate_key_different_job_type_still_rejected(self, db: Session):
        """Idempotency key is globally unique, not per-type."""
        _setup(db)
        enqueue_job(db, "drivers", {}, project_id="proj-a", idempotency_key="key-global")
        with pytest.raises(DuplicateJobError):
            enqueue_job(db, "segmentation", {}, project_id="proj-a", idempotency_key="key-global")

    def test_no_key_allows_duplicates(self, db: Session):
        """Without idempotency key, duplicate payloads are allowed."""
        _setup(db)
        j1 = enqueue_job(db, "drivers", {"x": 1}, project_id="proj-a")
        j2 = enqueue_job(db, "drivers", {"x": 1}, project_id="proj-a")
        assert j1.id != j2.id

    def test_get_job_by_idempotency_key(self, db: Session):
        _setup(db)
        job = enqueue_job(db, "drivers", {"x": 1}, idempotency_key="lookup-me")
        found = get_job_by_idempotency_key(db, "lookup-me")
        assert found is not None
        assert found.id == job.id

    def test_get_job_by_idempotency_key_not_found(self, db: Session):
        _setup(db)
        assert get_job_by_idempotency_key(db, "nonexistent") is None


# ---------------------------------------------------------------------------
# AC-3: Analysis run idempotency
# ---------------------------------------------------------------------------

class TestRunIdempotency:
    def test_create_new_run(self, db: Session):
        _setup(db)
        key = generate_idempotency_key("proj-a", "drivers")
        run, created = create_run_idempotent(db, "run-001", "proj-a", "drivers", key)
        assert created is True
        assert run.id == "run-001"
        assert run.idempotency_key == key

    def test_duplicate_returns_existing(self, db: Session):
        _setup(db)
        key = generate_idempotency_key("proj-a", "drivers")
        run1, c1 = create_run_idempotent(db, "run-001", "proj-a", "drivers", key)
        run2, c2 = create_run_idempotent(db, "run-002", "proj-a", "drivers", key)
        assert c1 is True
        assert c2 is False
        assert run2.id == run1.id  # returns existing

    def test_cross_project_collision_raises(self, db: Session):
        _setup(db)
        key = "shared-key-123"
        create_run_idempotent(db, "run-a", "proj-a", "drivers", key)
        with pytest.raises(DuplicateRunError):
            create_run_idempotent(db, "run-b", "proj-b", "drivers", key)

    def test_different_keys_create_separate_runs(self, db: Session):
        _setup(db)
        k1 = generate_idempotency_key("proj-a", "drivers", nonce="1")
        k2 = generate_idempotency_key("proj-a", "drivers", nonce="2")
        r1, _ = create_run_idempotent(db, "run-1", "proj-a", "drivers", k1)
        r2, _ = create_run_idempotent(db, "run-2", "proj-a", "drivers", k2)
        assert r1.id != r2.id

    def test_get_run_by_idempotency_key(self, db: Session):
        _setup(db)
        key = "find-me"
        create_run_idempotent(db, "run-x", "proj-a", "drivers", key)
        found = get_run_by_idempotency_key(db, key)
        assert found is not None
        assert found.id == "run-x"

    def test_get_run_by_idempotency_key_not_found(self, db: Session):
        _setup(db)
        assert get_run_by_idempotency_key(db, "no-such-key") is None

    def test_integrity_error_race_handled(self, db: Session):
        """Simulate TOCTOU: insert a row directly, then call create_run_idempotent."""
        _setup(db)
        key = "race-key"
        # Insert directly to simulate a concurrent insert that won the race
        sneaky = AnalysisRunRow(
            id="run-sneaky", project_id="proj-a", analysis_type="drivers",
            status="queued", idempotency_key=key,
        )
        db.add(sneaky)
        db.flush()
        # Now create_run_idempotent should find the existing row
        run, created = create_run_idempotent(db, "run-late", "proj-a", "drivers", key)
        assert created is False
        assert run.id == "run-sneaky"


# ---------------------------------------------------------------------------
# AC-4: Duplicate active run detection
# ---------------------------------------------------------------------------

class TestDuplicateActiveRun:
    def test_no_active_run(self, db: Session):
        _setup(db)
        assert check_duplicate_active_run(db, "proj-a", "drivers") is None

    def test_queued_run_detected(self, db: Session):
        _setup(db)
        repo.save_run(db, AnalysisRunRow(
            id="run-q1", project_id="proj-a", analysis_type="drivers", status="queued",
        ))
        db.commit()
        active = check_duplicate_active_run(db, "proj-a", "drivers")
        assert active is not None
        assert active.id == "run-q1"

    def test_running_run_detected(self, db: Session):
        _setup(db)
        repo.save_run(db, AnalysisRunRow(
            id="run-r1", project_id="proj-a", analysis_type="drivers", status="running",
        ))
        db.commit()
        active = check_duplicate_active_run(db, "proj-a", "drivers")
        assert active is not None
        assert active.id == "run-r1"

    def test_completed_run_not_detected(self, db: Session):
        _setup(db)
        repo.save_run(db, AnalysisRunRow(
            id="run-c1", project_id="proj-a", analysis_type="drivers", status="completed",
        ))
        db.commit()
        assert check_duplicate_active_run(db, "proj-a", "drivers") is None

    def test_failed_run_not_detected(self, db: Session):
        _setup(db)
        repo.save_run(db, AnalysisRunRow(
            id="run-f1", project_id="proj-a", analysis_type="drivers", status="failed",
        ))
        db.commit()
        assert check_duplicate_active_run(db, "proj-a", "drivers") is None

    def test_different_project_not_detected(self, db: Session):
        _setup(db)
        repo.save_run(db, AnalysisRunRow(
            id="run-b1", project_id="proj-b", analysis_type="drivers", status="queued",
        ))
        db.commit()
        assert check_duplicate_active_run(db, "proj-a", "drivers") is None

    def test_different_type_not_detected(self, db: Session):
        _setup(db)
        repo.save_run(db, AnalysisRunRow(
            id="run-seg", project_id="proj-a", analysis_type="segmentation", status="queued",
        ))
        db.commit()
        assert check_duplicate_active_run(db, "proj-a", "drivers") is None

    def test_multiple_active_detected(self, db: Session):
        """When multiple active runs exist, at least one is returned."""
        _setup(db)
        repo.save_run(db, AnalysisRunRow(
            id="run-old", project_id="proj-a", analysis_type="drivers", status="queued",
        ))
        repo.save_run(db, AnalysisRunRow(
            id="run-new", project_id="proj-a", analysis_type="drivers", status="running",
        ))
        db.commit()
        active = check_duplicate_active_run(db, "proj-a", "drivers")
        assert active is not None
        assert active.id in ("run-old", "run-new")
