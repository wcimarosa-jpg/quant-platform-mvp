"""Repository layer — CRUD operations for all entities.

Callers do NOT commit — the get_db() dependency handles commit/rollback.
Repository functions only add/modify; the session is flushed to make
IDs available but committed by the dependency at request end.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .models import (
    AnalysisRunRow,
    BriefRow,
    EventLogRow,
    MappingRow,
    ProjectRow,
    QuestionnaireRow,
)


def _valid_columns(model_class: type, keys: set[str]) -> set[str]:
    """Return the subset of keys that are actual column names on the model."""
    column_names = {c.key for c in model_class.__table__.columns}
    return keys & column_names


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

def create_project(db: Session, project_id: str, name: str, methodology: str) -> ProjectRow:
    row = ProjectRow(id=project_id, name=name, methodology=methodology)
    db.add(row)
    db.flush()
    return row


def get_project(db: Session, project_id: str) -> ProjectRow | None:
    return db.query(ProjectRow).filter(ProjectRow.id == project_id).first()


def list_projects(db: Session, limit: int = 100) -> list[ProjectRow]:
    return db.query(ProjectRow).order_by(ProjectRow.created_at.desc()).limit(limit).all()


# ---------------------------------------------------------------------------
# Briefs
# ---------------------------------------------------------------------------

def save_brief(db: Session, brief: BriefRow) -> BriefRow:
    db.add(brief)
    db.flush()
    return brief


def get_brief(db: Session, brief_id: str) -> BriefRow | None:
    return db.query(BriefRow).filter(BriefRow.id == brief_id).first()


def update_brief(db: Session, brief_id: str, updates: dict[str, Any]) -> BriefRow | None:
    brief = get_brief(db, brief_id)
    if not brief:
        return None
    valid = _valid_columns(BriefRow, set(updates.keys()))
    invalid = set(updates.keys()) - valid
    if invalid:
        raise ValueError(f"Unknown brief fields: {invalid}")
    for key in valid:
        setattr(brief, key, updates[key])
    db.flush()
    return brief


# ---------------------------------------------------------------------------
# Questionnaires
# ---------------------------------------------------------------------------

def save_questionnaire(db: Session, qre: QuestionnaireRow) -> QuestionnaireRow:
    db.add(qre)
    db.flush()
    return qre


def get_questionnaire(db: Session, qre_id: str) -> QuestionnaireRow | None:
    return db.query(QuestionnaireRow).filter(QuestionnaireRow.id == qre_id).first()


def list_questionnaire_versions(db: Session, project_id: str) -> list[QuestionnaireRow]:
    return (
        db.query(QuestionnaireRow)
        .filter(QuestionnaireRow.project_id == project_id)
        .order_by(QuestionnaireRow.version.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# Mappings
# ---------------------------------------------------------------------------

def save_mapping(db: Session, mapping: MappingRow) -> MappingRow:
    db.add(mapping)
    db.flush()
    return mapping


def get_mapping(db: Session, mapping_id: str) -> MappingRow | None:
    return db.query(MappingRow).filter(MappingRow.id == mapping_id).first()


def get_latest_mapping(db: Session, project_id: str) -> MappingRow | None:
    return (
        db.query(MappingRow)
        .filter(MappingRow.project_id == project_id)
        .order_by(MappingRow.version.desc())
        .first()
    )


# ---------------------------------------------------------------------------
# Analysis Runs
# ---------------------------------------------------------------------------

def save_run(db: Session, run: AnalysisRunRow) -> AnalysisRunRow:
    db.add(run)
    db.flush()
    return run


def get_run(db: Session, run_id: str) -> AnalysisRunRow | None:
    return db.query(AnalysisRunRow).filter(AnalysisRunRow.id == run_id).first()


def list_runs(db: Session, project_id: str, status: str | None = None, limit: int = 50) -> list[AnalysisRunRow]:
    q = db.query(AnalysisRunRow).filter(AnalysisRunRow.project_id == project_id)
    if status:
        q = q.filter(AnalysisRunRow.status == status)
    return q.order_by(AnalysisRunRow.created_at.desc()).limit(limit).all()


def update_run_status(db: Session, run_id: str, status: str, **kwargs: Any) -> AnalysisRunRow | None:
    run = get_run(db, run_id)
    if not run:
        return None
    run.status = status
    valid = _valid_columns(AnalysisRunRow, set(kwargs.keys()))
    invalid = set(kwargs.keys()) - valid
    if invalid:
        raise ValueError(f"Unknown run fields: {invalid}")
    for key in valid:
        setattr(run, key, kwargs[key])
    db.flush()
    return run


# ---------------------------------------------------------------------------
# Event Log
# ---------------------------------------------------------------------------

def log_event(
    db: Session,
    project_id: str | None,
    actor: str,
    event_type: str,
    category: str | None = None,
    action: str | None = None,
    payload: dict[str, Any] | None = None,
) -> EventLogRow:
    row = EventLogRow(
        project_id=project_id,
        actor=actor,
        event_type=event_type,
        category=category,
        action=action,
        payload_json=payload,
    )
    db.add(row)
    db.flush()
    return row


def list_events(
    db: Session,
    project_id: str | None = None,
    event_type: str | None = None,
    limit: int = 100,
) -> list[EventLogRow]:
    q = db.query(EventLogRow)
    if project_id:
        q = q.filter(EventLogRow.project_id == project_id)
    if event_type:
        q = q.filter(EventLogRow.event_type == event_type)
    return q.order_by(EventLogRow.created_at.desc()).limit(limit).all()
