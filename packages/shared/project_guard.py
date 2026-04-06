"""Project data isolation and storage boundary enforcement.

Service-layer guard that rejects cross-project access to artifacts.
Every DB query for project-scoped entities must go through these
guards to ensure the requesting user has access and the artifact
belongs to the specified project.

Integrates with:
- auth.py (check_project_access for membership/role)
- workspace.py (filesystem isolation)
- db/models.py (artifact ownership metadata)
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from .auth import check_project_access
from .db.models import (
    AnalysisRunRow,
    BriefRow,
    MappingRow,
    ProjectRow,
    QuestionnaireRow,
)

logger = logging.getLogger(__name__)


class ProjectAccessDenied(Exception):
    """Raised when a user attempts to access a project they don't belong to."""

    def __init__(self, user_id: str, project_id: str) -> None:
        self.user_id = user_id
        self.project_id = project_id
        super().__init__(f"Access denied: user {user_id!r} is not a member of project {project_id!r}.")


class CrossProjectAccessError(Exception):
    """Raised when an artifact is accessed from the wrong project context."""

    def __init__(self, artifact_type: str, artifact_id: str, expected_project: str, actual_project: str) -> None:
        self.artifact_type = artifact_type
        self.artifact_id = artifact_id
        self.expected_project = expected_project
        self.actual_project = actual_project
        # User-facing message redacts actual_project to prevent ownership info leakage
        super().__init__(
            f"Cross-project access blocked: {artifact_type} does not belong to project {expected_project!r}."
        )


# ---------------------------------------------------------------------------
# Artifact ownership verification
# ---------------------------------------------------------------------------

_ARTIFACT_MODELS = {
    "brief": BriefRow,
    "questionnaire": QuestionnaireRow,
    "mapping": MappingRow,
    "run": AnalysisRunRow,
}


def verify_artifact_ownership(
    db: Session,
    artifact_type: str,
    artifact_id: str,
    expected_project_id: str,
) -> Any:
    """Verify an artifact belongs to the expected project.

    Returns the artifact row if ownership matches.
    Raises CrossProjectAccessError if project_id doesn't match.
    Raises ValueError if artifact not found.
    """
    model_cls = _ARTIFACT_MODELS.get(artifact_type)
    if not model_cls:
        raise ValueError(f"Unknown artifact type: {artifact_type!r}")

    entity = db.query(model_cls).filter(model_cls.id == artifact_id).first()
    if not entity:
        raise ValueError(f"{artifact_type} {artifact_id!r} not found.")

    if entity.project_id != expected_project_id:
        logger.warning(
            "Cross-project access blocked: %s %s (project=%s) accessed from project=%s",
            artifact_type, artifact_id, entity.project_id, expected_project_id,
        )
        raise CrossProjectAccessError(
            artifact_type, artifact_id, expected_project_id, entity.project_id,
        )

    return entity


def guarded_get(
    db: Session,
    user_id: str,
    project_id: str,
    artifact_type: str,
    artifact_id: str,
    required_role: str = "reviewer",
) -> Any:
    """Full guard: check user access + artifact ownership.

    1. Verify user has access to the project (via membership/role).
    2. Verify the artifact belongs to that project.
    3. Return the artifact row.
    """
    if not check_project_access(db, user_id, project_id, required_role):
        raise ProjectAccessDenied(user_id, project_id)

    return verify_artifact_ownership(db, artifact_type, artifact_id, project_id)


def guarded_list(
    db: Session,
    user_id: str,
    project_id: str,
    artifact_type: str,
    required_role: str = "reviewer",
    limit: int = 100,
) -> list[Any]:
    """List artifacts within a project with access guard.

    Only returns artifacts belonging to the specified project.
    """
    if not check_project_access(db, user_id, project_id, required_role):
        raise ProjectAccessDenied(user_id, project_id)

    model_cls = _ARTIFACT_MODELS.get(artifact_type)
    if not model_cls:
        raise ValueError(f"Unknown artifact type: {artifact_type!r}")

    limit = max(1, min(limit, 500))

    return (
        db.query(model_cls)
        .filter(model_cls.project_id == project_id)
        .order_by(model_cls.created_at.desc())
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# Ownership tagging helper
# ---------------------------------------------------------------------------

def tag_artifact_ownership(entity: Any, project_id: str) -> None:
    """Ensure an artifact has its project_id set correctly.

    Call this before persisting any new artifact to enforce ownership tagging.
    Raises ValueError if entity already has a different project_id.
    """
    current = getattr(entity, "project_id", None)
    if current and current != project_id:
        raise ValueError(
            f"Cannot re-tag artifact: already owned by project {current!r}, "
            f"attempted to tag with {project_id!r}."
        )
    entity.project_id = project_id
