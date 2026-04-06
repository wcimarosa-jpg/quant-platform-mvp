"""Initial schema — all tables as of P09-06.

Revision ID: 001
Revises: None
Create Date: 2026-04-06
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Projects
    op.create_table(
        "projects",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("methodology", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    # Briefs
    op.create_table(
        "briefs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("objectives", sa.Text()),
        sa.Column("audience", sa.Text()),
        sa.Column("category", sa.String(255)),
        sa.Column("geography", sa.String(255)),
        sa.Column("constraints", sa.Text()),
        sa.Column("raw_text", sa.Text()),
        sa.Column("source_filename", sa.String(255)),
        sa.Column("source_format", sa.String(20)),
        sa.Column("version_token", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    # Questionnaires
    op.create_table(
        "questionnaires",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("methodology", sa.String(50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sections_json", sa.JSON(), nullable=False),
        sa.Column("total_questions", sa.Integer(), server_default="0"),
        sa.Column("estimated_loi", sa.Integer(), server_default="0"),
        sa.Column("draft_id", sa.String(64)),
        sa.Column("brief_id", sa.String(64)),
        sa.Column("context_hash", sa.String(32)),
        sa.Column("version_token", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_qre_project_version", "questionnaires", ["project_id", "version"])

    # Mappings
    op.create_table(
        "mappings",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("questionnaire_id", sa.String(64)),
        sa.Column("questionnaire_version", sa.Integer()),
        sa.Column("data_file_hash", sa.String(80)),
        sa.Column("mappings_json", sa.JSON(), nullable=False),
        sa.Column("unmapped_columns_json", sa.JSON()),
        sa.Column("locked", sa.Boolean(), server_default="0"),
        sa.Column("version_token", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_map_project_version", "mappings", ["project_id", "version"])

    # Analysis Runs
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("idempotency_key", sa.String(255), unique=True, nullable=True),
        sa.Column("config_json", sa.JSON()),
        sa.Column("versions_json", sa.JSON()),
        sa.Column("result_summary_json", sa.JSON()),
        sa.Column("error_message", sa.Text()),
        sa.Column("error_type", sa.String(50)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_run_project_status", "analysis_runs", ["project_id", "status"])

    # Event Log
    op.create_table(
        "event_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.String(64), index=True),
        sa.Column("actor", sa.String(100)),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("category", sa.String(50)),
        sa.Column("action", sa.String(100)),
        sa.Column("payload_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_event_project_type", "event_log", ["project_id", "event_type"])

    # Users
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="researcher"),
        sa.Column("is_active", sa.Boolean(), server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Project Memberships
    op.create_table(
        "project_memberships",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="researcher"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_membership_user_project", "project_memberships", ["user_id", "project_id"], unique=True)

    # Audit Log
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("actor_id", sa.String(64), index=True),
        sa.Column("actor_email", sa.String(255)),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("project_id", sa.String(64), index=True),
        sa.Column("artifact_type", sa.String(50)),
        sa.Column("artifact_id", sa.String(64)),
        sa.Column("detail", sa.Text()),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_audit_actor_action", "audit_log", ["actor_id", "action"])

    # Job Queue
    op.create_table(
        "job_queue",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("job_type", sa.String(100), nullable=False),
        sa.Column("project_id", sa.String(64), index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("idempotency_key", sa.String(255), unique=True, nullable=True),
        sa.Column("payload_json", sa.JSON()),
        sa.Column("result_json", sa.JSON()),
        sa.Column("error_message", sa.Text()),
        sa.Column("error_type", sa.String(50)),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("dead_letter", sa.Boolean(), server_default="0"),
    )
    op.create_index("ix_job_status", "job_queue", ["status"])


def downgrade() -> None:
    # Drop indexes before tables for PostgreSQL portability
    op.drop_index("ix_job_status", table_name="job_queue")
    op.drop_table("job_queue")

    op.drop_index("ix_audit_actor_action", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index("ix_membership_user_project", table_name="project_memberships")
    op.drop_table("project_memberships")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_event_project_type", table_name="event_log")
    op.drop_table("event_log")

    op.drop_index("ix_run_project_status", table_name="analysis_runs")
    op.drop_table("analysis_runs")

    op.drop_index("ix_map_project_version", table_name="mappings")
    op.drop_table("mappings")

    op.drop_index("ix_qre_project_version", table_name="questionnaires")
    op.drop_table("questionnaires")

    op.drop_table("briefs")
    op.drop_table("projects")
