"""Migration runner — programmatic Alembic interface.

Provides functions to run migrations, check current revision,
and verify migration state. Used by CI, tests, and startup checks.
"""

from __future__ import annotations

import os
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import pool

logger = logging.getLogger(__name__)

# Locate alembic.ini relative to this file (project root)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_INI = _PROJECT_ROOT / "alembic.ini"


def _get_alembic_config(db_url: str | None = None) -> Config:
    """Build an Alembic Config, optionally overriding the DB URL."""
    cfg = Config(str(_ALEMBIC_INI))
    if db_url:
        cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def run_upgrade(db_url: str | None = None, revision: str = "head") -> None:
    """Run migrations up to the given revision (default: head)."""
    cfg = _get_alembic_config(db_url)
    command.upgrade(cfg, revision)
    logger.info("Migrations upgraded to %s", revision)


def run_downgrade(db_url: str | None = None, revision: str = "-1") -> None:
    """Run migrations down by the given amount (default: one step back)."""
    cfg = _get_alembic_config(db_url)
    command.downgrade(cfg, revision)
    logger.info("Migrations downgraded to %s", revision)


def get_current_revision(db_url: str | None = None) -> str | None:
    """Return the current migration revision, or None if not stamped."""
    cfg = _get_alembic_config(db_url)

    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    url = db_url or cfg.get_main_option("sqlalchemy.url")
    engine = create_engine(url, poolclass=pool.NullPool)
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            return ctx.get_current_revision()
    finally:
        engine.dispose()


def get_head_revision() -> str:
    """Return the latest migration revision ID."""
    cfg = _get_alembic_config()
    script = ScriptDirectory.from_config(cfg)
    return script.get_current_head()


def is_up_to_date(db_url: str | None = None) -> bool:
    """Check if the database is at the latest migration revision."""
    current = get_current_revision(db_url)
    head = get_head_revision()
    return current == head


def pending_migrations(db_url: str | None = None) -> list[str]:
    """Return list of pending migration revision IDs."""
    cfg = _get_alembic_config(db_url)
    script = ScriptDirectory.from_config(cfg)
    current = get_current_revision(db_url)

    # Collect all revisions from base to head
    all_revs = []
    rev = script.get_revision(script.get_current_head())
    while rev is not None:
        all_revs.append(rev.revision)
        rev = script.get_revision(rev.down_revision) if rev.down_revision else None
    all_revs.reverse()

    if current is None:
        return all_revs

    try:
        idx = all_revs.index(current)
        return all_revs[idx + 1:]
    except ValueError:
        return all_revs
