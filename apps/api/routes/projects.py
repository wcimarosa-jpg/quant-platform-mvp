"""Project CRUD routes — scoped to authenticated user."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.auth_deps import CurrentUser
from packages.shared.auth import get_user_projects, add_project_member, Role
from packages.shared.db import repository as repo
from packages.shared.db.engine import get_db

router = APIRouter(prefix="/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str
    methodology: str


@router.get("/")
def list_projects(user: CurrentUser, db: Session = Depends(get_db)) -> dict[str, Any]:
    """List projects accessible to the authenticated user."""
    if user.role == Role.ADMIN.value:
        # Admins see all projects
        from packages.shared.db.models import ProjectRow
        rows = db.query(ProjectRow).order_by(ProjectRow.created_at.desc()).limit(100).all()
    else:
        project_ids = get_user_projects(db, user.sub)
        from packages.shared.db.models import ProjectRow
        rows = db.query(ProjectRow).filter(ProjectRow.id.in_(project_ids)).all() if project_ids else []

    projects = [
        {
            "id": p.id,
            "name": p.name,
            "methodology": p.methodology,
            "status": p.status,
        }
        for p in rows
    ]
    return {"projects": projects, "total": len(projects)}


@router.post("/")
def create_project(
    body: CreateProjectRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a new project owned by the authenticated user."""
    project = repo.create_project(db, f"proj-{__import__('uuid').uuid4().hex[:12]}", body.name, body.methodology)
    # Add creator as researcher member
    add_project_member(db, user.sub, project.id, user.role)
    return {
        "id": project.id,
        "name": project.name,
        "methodology": project.methodology,
        "status": project.status,
    }
