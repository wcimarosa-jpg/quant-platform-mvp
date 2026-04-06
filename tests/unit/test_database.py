"""Tests for P09-01: Database persistence layer.

AC-1: All runtime state migrated with parity checks.
AC-2: Connection pooling and transaction boundaries.
AC-3: Concurrent read/write (SQLite WAL; PostgreSQL integration test deferred).
"""

from __future__ import annotations

import threading

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from packages.shared.db.models import (
    AnalysisRunRow,
    Base,
    BriefRow,
    EventLogRow,
    MappingRow,
    ProjectRow,
    QuestionnaireRow,
)
from packages.shared.db import repository as repo


@pytest.fixture
def db() -> Session:
    """Fresh in-memory SQLite for each test. Commits after each repo call
    to simulate get_db() behavior."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    yield session
    session.close()


def _commit(db: Session):
    """Simulate get_db() commit at request boundary."""
    db.commit()


# ---------------------------------------------------------------------------
# AC-1: CRUD parity
# ---------------------------------------------------------------------------

class TestProjectCRUD:
    def test_create_and_get(self, db: Session):
        repo.create_project(db, "proj-001", "Test Project", "segmentation")
        _commit(db)
        retrieved = repo.get_project(db, "proj-001")
        assert retrieved is not None
        assert retrieved.methodology == "segmentation"

    def test_list_projects(self, db: Session):
        repo.create_project(db, "proj-a", "A", "drivers")
        repo.create_project(db, "proj-b", "B", "segmentation")
        _commit(db)
        assert len(repo.list_projects(db)) == 2

    def test_get_nonexistent(self, db: Session):
        assert repo.get_project(db, "nope") is None


class TestBriefCRUD:
    def test_save_and_get(self, db: Session):
        repo.create_project(db, "proj-001", "P", "seg")
        repo.save_brief(db, BriefRow(id="brief-001", project_id="proj-001", objectives="Test"))
        _commit(db)
        assert repo.get_brief(db, "brief-001").objectives == "Test"

    def test_update_brief(self, db: Session):
        repo.create_project(db, "proj-001", "P", "seg")
        repo.save_brief(db, BriefRow(id="brief-001", project_id="proj-001", objectives="Old"))
        _commit(db)
        updated = repo.update_brief(db, "brief-001", {"objectives": "New", "audience": "Adults"})
        _commit(db)
        assert updated.objectives == "New"
        assert updated.audience == "Adults"

    def test_update_invalid_field_raises(self, db: Session):
        repo.create_project(db, "proj-001", "P", "seg")
        repo.save_brief(db, BriefRow(id="brief-001", project_id="proj-001", objectives="X"))
        _commit(db)
        with pytest.raises(ValueError, match="Unknown"):
            repo.update_brief(db, "brief-001", {"nonexistent_field": "bad"})


class TestQuestionnaireCRUD:
    def test_save_and_get(self, db: Session):
        repo.create_project(db, "proj-001", "P", "seg")
        repo.save_questionnaire(db, QuestionnaireRow(
            id="qre-001", project_id="proj-001", methodology="seg",
            version=1, sections_json=[{"type": "screener"}],
        ))
        _commit(db)
        assert repo.get_questionnaire(db, "qre-001").sections_json == [{"type": "screener"}]

    def test_version_listing(self, db: Session):
        repo.create_project(db, "proj-001", "P", "seg")
        for v in [1, 2, 3]:
            repo.save_questionnaire(db, QuestionnaireRow(
                id=f"qre-v{v}", project_id="proj-001", methodology="seg",
                version=v, sections_json=[],
            ))
        _commit(db)
        versions = repo.list_questionnaire_versions(db, "proj-001")
        assert len(versions) == 3
        assert versions[0].version == 3


class TestMappingCRUD:
    def test_save_and_get_latest(self, db: Session):
        repo.create_project(db, "proj-001", "P", "seg")
        for v in [1, 2]:
            repo.save_mapping(db, MappingRow(
                id=f"map-v{v}", project_id="proj-001", version=v,
                mappings_json=[{"col": "A", "var": "B"}],
            ))
        _commit(db)
        assert repo.get_latest_mapping(db, "proj-001").version == 2


class TestRunCRUD:
    def test_save_and_update(self, db: Session):
        repo.create_project(db, "proj-001", "P", "seg")
        repo.save_run(db, AnalysisRunRow(
            id="run-001", project_id="proj-001", analysis_type="drivers", status="queued",
        ))
        _commit(db)
        updated = repo.update_run_status(db, "run-001", "completed", duration_ms=1500)
        _commit(db)
        assert updated.status == "completed"
        assert updated.duration_ms == 1500

    def test_update_invalid_field_raises(self, db: Session):
        repo.create_project(db, "proj-001", "P", "seg")
        repo.save_run(db, AnalysisRunRow(
            id="run-001", project_id="proj-001", analysis_type="d", status="queued",
        ))
        _commit(db)
        with pytest.raises(ValueError, match="Unknown"):
            repo.update_run_status(db, "run-001", "completed", fake_field="bad")

    def test_list_by_status(self, db: Session):
        repo.create_project(db, "proj-001", "P", "seg")
        repo.save_run(db, AnalysisRunRow(id="r1", project_id="proj-001", analysis_type="d", status="completed"))
        repo.save_run(db, AnalysisRunRow(id="r2", project_id="proj-001", analysis_type="d", status="failed"))
        _commit(db)
        assert len(repo.list_runs(db, "proj-001", status="completed")) == 1


class TestEventLog:
    def test_log_and_list(self, db: Session):
        repo.log_event(db, "proj-001", "user", "project.created", payload={"name": "Test"})
        repo.log_event(db, "proj-001", "assistant", "brief.parsed")
        _commit(db)
        assert len(repo.list_events(db, project_id="proj-001")) == 2

    def test_filter_by_type(self, db: Session):
        repo.log_event(db, "proj-001", "user", "project.created")
        repo.log_event(db, "proj-001", "user", "brief.uploaded")
        _commit(db)
        assert len(repo.list_events(db, event_type="project.created")) == 1


# ---------------------------------------------------------------------------
# AC-2: Transaction boundaries
# ---------------------------------------------------------------------------

class TestTransactions:
    def test_multi_op_atomic(self, db: Session):
        """Multiple repo calls in one transaction commit together."""
        repo.create_project(db, "proj-atom", "P", "seg")
        repo.save_brief(db, BriefRow(id="b1", project_id="proj-atom", objectives="X"))
        _commit(db)
        assert repo.get_project(db, "proj-atom") is not None
        assert repo.get_brief(db, "b1") is not None

    def test_rollback_on_error(self, db: Session):
        repo.create_project(db, "proj-001", "P", "seg")
        _commit(db)
        try:
            repo.create_project(db, "proj-001", "Duplicate", "seg")
            _commit(db)
        except Exception:
            db.rollback()
        assert repo.get_project(db, "proj-001").name == "P"

    def test_cascade_delete(self, db: Session):
        repo.create_project(db, "proj-del", "P", "seg")
        repo.save_brief(db, BriefRow(id="b1", project_id="proj-del", objectives="X"))
        _commit(db)
        project = repo.get_project(db, "proj-del")
        db.delete(project)
        _commit(db)
        assert repo.get_brief(db, "b1") is None


# ---------------------------------------------------------------------------
# AC-3: Concurrent read/write (SQLite WAL)
# NOTE: PostgreSQL concurrency should be tested via integration tests.
# ---------------------------------------------------------------------------

class TestConcurrency:
    def test_7_concurrent_writers(self, tmp_path):
        """7 threads writing simultaneously — no corruption."""
        db_path = str(tmp_path / "concurrent.db")
        eng = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(eng)
        raw = eng.raw_connection()
        raw.execute("PRAGMA journal_mode=WAL")
        raw.execute("PRAGMA busy_timeout=5000")
        raw.close()

        Sess = sessionmaker(bind=eng)
        errors: list[str] = []

        def _worker(wid: int):
            try:
                s = Sess()
                s.add(ProjectRow(id=f"proj-{wid}", name=f"P{wid}", methodology="seg"))
                s.commit()
                assert s.query(ProjectRow).filter(ProjectRow.id == f"proj-{wid}").first() is not None
                s.close()
            except Exception as exc:
                errors.append(f"Worker {wid}: {exc}")

        threads = [threading.Thread(target=_worker, args=(i,)) for i in range(7)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Concurrency errors: {errors}"
        s = Sess()
        assert s.query(ProjectRow).count() == 7
        s.close()
