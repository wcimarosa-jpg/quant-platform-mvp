"""Database engine configuration.

Supports SQLite (dev) and PostgreSQL (prod) via a single DATABASE_URL.
Connection pooling configured for concurrent access.

Env vars:
    DATABASE_URL: sqlite:///./app.db (default) or postgresql://user:pass@host/db
"""

from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./quant_platform.db")

_is_sqlite = DATABASE_URL.startswith("sqlite")

# Engine configuration
_engine_kwargs: dict = {}
if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL: connection pooling for concurrent users
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20
    _engine_kwargs["pool_pre_ping"] = True
    _engine_kwargs["pool_recycle"] = 300  # recycle stale connections (5 min)

engine = create_engine(DATABASE_URL, echo=False, **_engine_kwargs)

# Enable WAL mode for SQLite concurrent reads
if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_wal(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI route injection.

    Commits on success, rolls back on exception, always closes.
    Callers should NOT call db.commit() — the dependency handles it.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def is_sqlite() -> bool:
    return _is_sqlite
