"""SQLAlchemy ORM models for the quant platform.

Covers all entities previously stored in-memory:
projects, briefs, questionnaires, mappings, analysis runs, events.

Works with both SQLite and PostgreSQL.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class ProjectRow(Base):
    __tablename__ = "projects"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    methodology = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    briefs = relationship("BriefRow", back_populates="project", cascade="all, delete-orphan")
    questionnaires = relationship("QuestionnaireRow", back_populates="project", cascade="all, delete-orphan")
    mappings = relationship("MappingRow", back_populates="project", cascade="all, delete-orphan")
    runs = relationship("AnalysisRunRow", back_populates="project", cascade="all, delete-orphan")


class BriefRow(Base):
    __tablename__ = "briefs"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    objectives = Column(Text)
    audience = Column(Text)
    category = Column(String(255))
    geography = Column(String(255))
    constraints = Column(Text)
    raw_text = Column(Text)
    source_filename = Column(String(255))
    source_format = Column(String(20))
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    project = relationship("ProjectRow", back_populates="briefs")


class QuestionnaireRow(Base):
    __tablename__ = "questionnaires"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    methodology = Column(String(50), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    sections_json = Column(JSON, nullable=False)      # serialized Section list
    total_questions = Column(Integer, default=0)
    estimated_loi = Column(Integer, default=0)
    draft_id = Column(String(64))
    brief_id = Column(String(64))
    context_hash = Column(String(32))
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    project = relationship("ProjectRow", back_populates="questionnaires")

    __table_args__ = (
        Index("ix_qre_project_version", "project_id", "version"),
    )


class MappingRow(Base):
    __tablename__ = "mappings"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    questionnaire_id = Column(String(64))
    questionnaire_version = Column(Integer)
    data_file_hash = Column(String(80))
    mappings_json = Column(JSON, nullable=False)     # serialized ColumnMapping list
    unmapped_columns_json = Column(JSON)
    locked = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    project = relationship("ProjectRow", back_populates="mappings")

    __table_args__ = (
        Index("ix_map_project_version", "project_id", "version"),
    )


class AnalysisRunRow(Base):
    __tablename__ = "analysis_runs"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    analysis_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="queued")
    config_json = Column(JSON)
    versions_json = Column(JSON)
    result_summary_json = Column(JSON)
    error_message = Column(Text)
    error_type = Column(String(50))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    project = relationship("ProjectRow", back_populates="runs")

    __table_args__ = (
        Index("ix_run_project_status", "project_id", "status"),
    )


class EventLogRow(Base):
    __tablename__ = "event_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(64), index=True)
    actor = Column(String(100))
    event_type = Column(String(100), nullable=False)
    category = Column(String(50))
    action = Column(String(100))
    payload_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_event_project_type", "project_id", "event_type"),
    )
