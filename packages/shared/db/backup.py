"""Database backup and restore utilities.

Supports SQLite file-level backup and JSON-based dump/restore
for both SQLite and PostgreSQL. Designed for disaster recovery drills.

Usage:
    from packages.shared.db.backup import backup_sqlite, restore_sqlite
    backup_sqlite("quant_platform.db", "backups/quant_platform_2026-04-06.db")
    restore_sqlite("backups/quant_platform_2026-04-06.db", "quant_platform.db")
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from .models import Base

logger = logging.getLogger(__name__)


class BackupError(Exception):
    """Raised when a backup or restore operation fails."""


class RestoreError(Exception):
    """Raised when a restore operation fails."""


# ---------------------------------------------------------------------------
# SQLite file-level backup
# ---------------------------------------------------------------------------

def backup_sqlite(source_path: str, dest_path: str) -> str:
    """Copy a SQLite database file to a backup location.

    Uses sqlite3 backup API for a consistent snapshot even if the DB
    is being written to. Cleans up partial dest on failure. Returns dest_path.
    """
    source_path = os.path.abspath(source_path)
    dest_path = os.path.abspath(dest_path)

    if not os.path.isfile(source_path):
        raise BackupError(f"Source database not found: {source_path}")

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    src_conn = sqlite3.connect(source_path)
    dst_conn = sqlite3.connect(dest_path)
    try:
        src_conn.backup(dst_conn)
        logger.info("SQLite backup: %s -> %s", source_path, dest_path)
    except Exception:
        dst_conn.close()
        src_conn.close()
        # Clean up partial backup file
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise
    finally:
        dst_conn.close()
        src_conn.close()

    return dest_path


def restore_sqlite(backup_path: str, dest_path: str) -> str:
    """Restore a SQLite database from a backup file.

    Replaces the destination database with the backup. Returns dest_path.
    """
    backup_path = os.path.abspath(backup_path)
    dest_path = os.path.abspath(dest_path)

    if not os.path.isfile(backup_path):
        raise RestoreError(f"Backup file not found: {backup_path}")

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    src_conn = sqlite3.connect(backup_path)
    dst_conn = sqlite3.connect(dest_path)
    try:
        src_conn.backup(dst_conn)
        logger.info("SQLite restore: %s -> %s", backup_path, dest_path)
    finally:
        dst_conn.close()
        src_conn.close()

    return dest_path


# ---------------------------------------------------------------------------
# JSON dump backup/restore (works with any engine)
# ---------------------------------------------------------------------------

def dump_to_json(db: Session) -> dict[str, Any]:
    """Export all tables to a JSON-serializable dict.

    Returns {"metadata": {...}, "tables": {"table_name": [rows...]}}
    where each row is a dict of column_name: value.

    Suitable for cross-engine backup (SQLite -> PostgreSQL and vice versa).
    """
    inspector = inspect(db.get_bind())
    table_names = inspector.get_table_names()

    # Filter to only our known tables
    known_tables = {t.name for t in Base.metadata.sorted_tables}
    table_names = [t for t in table_names if t in known_tables]

    dump: dict[str, Any] = {
        "metadata": {
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "table_count": len(table_names),
            "tables": table_names,
        },
        "tables": {},
    }

    for table_name in table_names:
        # Use metadata table object to avoid SQL injection via string interpolation
        table = Base.metadata.tables[table_name]
        rows = db.execute(table.select()).fetchall()
        columns = [col.name for col in table.columns]
        dump["tables"][table_name] = [
            {col: _serialize(val) for col, val in zip(columns, row)}
            for row in rows
        ]
        dump["metadata"][f"{table_name}_count"] = len(rows)

    return dump


def _serialize(val: Any) -> Any:
    """Make a value JSON-serializable."""
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, bytes):
        return val.hex()
    return val


def _deserialize_row(table, row: dict[str, Any]) -> dict[str, Any]:
    """Convert serialized values back to Python types for insertion."""
    from sqlalchemy import DateTime as SADateTime

    result = {}
    col_types = {c.name: c.type for c in table.columns}
    for key, val in row.items():
        if val is not None and isinstance(col_types.get(key), SADateTime) and isinstance(val, str):
            try:
                result[key] = datetime.fromisoformat(val)
            except (ValueError, TypeError):
                result[key] = val
        else:
            result[key] = val
    return result


def restore_from_json(
    db: Session,
    dump: dict[str, Any],
    allow_non_empty: bool = False,
) -> dict[str, int]:
    """Restore tables from a JSON dump.

    Inserts rows in dependency order (respecting foreign keys).
    Returns a dict of table_name: rows_inserted.

    By default, raises RestoreError if any target table already has data.
    Pass allow_non_empty=True to skip this check (use with caution).
    """
    tables_data = dump.get("tables", {})
    if not tables_data:
        raise RestoreError("Dump contains no table data.")

    # Safety: check target tables are empty unless explicitly allowed
    if not allow_non_empty:
        for table_name in tables_data:
            if table_name in Base.metadata.tables:
                table = Base.metadata.tables[table_name]
                count = db.execute(table.select().limit(1)).first()
                if count is not None:
                    raise RestoreError(
                        f"Table {table_name!r} is not empty. "
                        f"Pass allow_non_empty=True to override."
                    )

    # Insert in dependency order (sorted_tables respects FK ordering)
    insert_order = [t.name for t in Base.metadata.sorted_tables]
    counts: dict[str, int] = {}

    for table_name in insert_order:
        rows = tables_data.get(table_name, [])
        if not rows:
            counts[table_name] = 0
            continue

        table = Base.metadata.tables[table_name]
        deserialized = [_deserialize_row(table, r) for r in rows]
        db.execute(table.insert(), deserialized)
        counts[table_name] = len(rows)
        logger.info("Restored %d rows to %s", len(rows), table_name)

    db.flush()
    return counts


def dump_to_file(db: Session, path: str) -> str:
    """Dump database to a JSON file. Returns the file path."""
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = dump_to_json(db)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    logger.info("Database dumped to %s (%d tables)", path, data["metadata"]["table_count"])
    return path


def restore_from_file(
    db: Session,
    path: str,
    allow_non_empty: bool = False,
) -> dict[str, int]:
    """Restore database from a JSON dump file. Returns row counts."""
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise RestoreError(f"Dump file not found: {path}")
    with open(path) as f:
        data = json.load(f)
    return restore_from_json(db, data, allow_non_empty=allow_non_empty)


# ---------------------------------------------------------------------------
# Integrity verification
# ---------------------------------------------------------------------------

def verify_integrity(db: Session) -> dict[str, Any]:
    """Run integrity checks on the database.

    Returns a dict with check results. Useful for post-restore validation.
    """
    inspector = inspect(db.get_bind())
    results: dict[str, Any] = {
        "tables_found": [],
        "tables_missing": [],
        "row_counts": {},
        "fk_violations": [],
    }

    known_tables = {t.name for t in Base.metadata.sorted_tables}
    actual_tables = set(inspector.get_table_names())

    results["tables_found"] = sorted(known_tables & actual_tables)
    results["tables_missing"] = sorted(known_tables - actual_tables)

    for table_name in results["tables_found"]:
        table = Base.metadata.tables[table_name]
        count = db.scalar(select(func.count()).select_from(table))
        results["row_counts"][table_name] = count

    # SQLite-specific: PRAGMA foreign_key_check
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        try:
            violations = db.execute(text("PRAGMA foreign_key_check")).fetchall()
            results["fk_violations"] = [
                {"table": v[0], "rowid": v[1], "parent": v[2], "fkid": v[3]}
                for v in violations
            ]
        except Exception:
            pass

    results["ok"] = len(results["tables_missing"]) == 0 and len(results["fk_violations"]) == 0
    return results
