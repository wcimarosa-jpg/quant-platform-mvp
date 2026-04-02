"""Project CRUD stub routes."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/")
def list_projects() -> dict[str, object]:
    return {"projects": [], "total": 0}


@router.post("/")
def create_project(name: str, methodology: str) -> dict[str, object]:
    return {
        "id": "proj-stub",
        "name": name,
        "methodology": methodology,
        "status": "created",
    }
