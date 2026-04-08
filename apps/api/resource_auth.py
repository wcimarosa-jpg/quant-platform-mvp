"""Resource-level authorization for in-memory stores.

Provides helpers for tracking and enforcing ownership on resources stored
in the temporary in-memory dicts (briefs, drafts, tables runs, QA reports).
This bridges the gap until those stores are migrated to the database where
project_guard.py can enforce DB-backed authorization.

Pattern:
    # On create:
    record_ownership(brief_id, owner_id=user.sub, project_id=project_id)

    # On read/update:
    require_owner(brief_id, user)
"""

from __future__ import annotations

from threading import Lock
from typing import Any

from fastapi import HTTPException

from packages.shared.auth import TokenPayload


# resource_id -> {"owner_id": str, "project_id": str}
_owners: dict[str, dict[str, str]] = {}
_lock = Lock()


def record_ownership(resource_id: str, owner_id: str, project_id: str = "") -> None:
    """Track that a resource was created by a given user under a project."""
    with _lock:
        _owners[resource_id] = {"owner_id": owner_id, "project_id": project_id}


def get_ownership(resource_id: str) -> dict[str, str] | None:
    """Return ownership metadata for a resource, or None if not tracked."""
    with _lock:
        return _owners.get(resource_id)


def require_owner(resource_id: str, user: TokenPayload) -> None:
    """Raise 403 if the current user does not own the resource.

    Admins bypass ownership checks. If the resource has no recorded owner
    (legacy data), it is treated as inaccessible to non-admins.
    """
    if user.role == "admin":
        return

    meta = get_ownership(resource_id)
    if not meta:
        raise HTTPException(
            status_code=404,
            detail=f"Resource {resource_id!r} not found or access denied.",
        )

    if meta["owner_id"] != user.sub:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this resource.",
        )


def clear_ownership(resource_id: str) -> None:
    """Remove ownership tracking (for testing or resource deletion)."""
    with _lock:
        _owners.pop(resource_id, None)


def reset_all_ownership() -> None:
    """Clear all ownership records (for testing)."""
    with _lock:
        _owners.clear()
