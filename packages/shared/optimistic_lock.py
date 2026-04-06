"""Optimistic locking and conflict resolution.

Prevents silent overwrites when multiple users edit the same artifact.
Every update requires a version_token; if stale, returns a ConflictError
with merge/retry guidance.

Uses atomic UPDATE ... WHERE version_token = :expected for race safety.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session

from .db.models import BriefRow, MappingRow, QuestionnaireRow


class ConflictError(Exception):
    """Raised when an update conflicts with a concurrent edit."""

    def __init__(
        self,
        entity_type: str,
        entity_id: str,
        expected_token: int,
        actual_token: int,
    ) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.expected_token = expected_token
        self.actual_token = actual_token
        super().__init__(
            f"Conflict on {entity_type} {entity_id!r}: "
            f"your version_token={expected_token}, current={actual_token}. "
            f"Refresh and retry."
        )

    def to_response(self) -> dict[str, Any]:
        """Structured response for API conflict (HTTP 409)."""
        return {
            "error": "conflict",
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "your_version_token": self.expected_token,
            "current_version_token": self.actual_token,
            "guidance": "Refresh the entity to get the latest version, "
                        "then re-apply your changes and submit with the "
                        "updated version_token.",
        }


_LOCKABLE_MODELS = {
    "brief": BriefRow,
    "questionnaire": QuestionnaireRow,
    "mapping": MappingRow,
}

# Fields that cannot be overwritten via updates
_PROTECTED_FIELDS = {"id", "version_token", "created_at", "project_id"}


def optimistic_update(
    db: Session,
    entity_type: str,
    entity_id: str,
    expected_token: int,
    updates: dict[str, Any],
) -> Any:
    """Atomically update an entity only if version_token matches.

    Uses UPDATE ... WHERE id=:id AND version_token=:expected to prevent
    TOCTOU races under concurrent access.

    On success: applies updates, increments version_token, returns entity.
    On conflict: raises ConflictError with merge guidance.
    """
    model_cls = _LOCKABLE_MODELS.get(entity_type)
    if not model_cls:
        raise ValueError(f"Unsupported entity_type for locking: {entity_type!r}")

    # Build the SET clause — filter out protected fields
    set_values: dict[str, Any] = {}
    for key, value in updates.items():
        if key not in _PROTECTED_FIELDS and hasattr(model_cls, key):
            set_values[key] = value
    set_values["version_token"] = expected_token + 1

    # Atomic UPDATE with WHERE version_token check
    stmt = (
        update(model_cls)
        .where(model_cls.id == entity_id, model_cls.version_token == expected_token)
        .values(**set_values)
    )
    result = db.execute(stmt)

    if result.rowcount == 0:
        # Either entity doesn't exist or token was stale
        entity = db.query(model_cls).filter(model_cls.id == entity_id).first()
        if not entity:
            raise ValueError(f"{entity_type} {entity_id!r} not found.")
        raise ConflictError(entity_type, entity_id, expected_token, entity.version_token)

    db.flush()
    # Refresh and return the updated entity
    entity = db.query(model_cls).filter(model_cls.id == entity_id).first()
    return entity


def get_version_token(db: Session, entity_type: str, entity_id: str) -> int:
    """Get the current version_token for an entity."""
    model_cls = _LOCKABLE_MODELS.get(entity_type)
    if not model_cls:
        raise ValueError(f"Unsupported entity_type: {entity_type!r}")
    entity = db.query(model_cls).filter(model_cls.id == entity_id).first()
    if not entity:
        raise ValueError(f"{entity_type} {entity_id!r} not found.")
    return entity.version_token
