"""Project workspace service with hard isolation boundaries.

Creates and manages per-project directory structures.
All filesystem access goes through this module, which enforces
that no path can escape its project root.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_SUBDIRS = (
    "Briefs",
    "Questionnaires",
    "Data",
    "Mappings",
    "Runs",
    "Outputs",
    "Logs",
)

_PROJECT_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,62}$")


class WorkspaceError(Exception):
    """Base error for workspace operations."""


class ProjectNotFoundError(WorkspaceError):
    """Raised when a project directory does not exist."""


class PathTraversalError(WorkspaceError):
    """Raised when a path attempts to escape the project boundary."""


class InvalidProjectIdError(WorkspaceError):
    """Raised when a project ID fails validation."""


def _validate_project_id(project_id: str) -> None:
    if not _PROJECT_ID_RE.match(project_id):
        raise InvalidProjectIdError(
            f"Invalid project ID {project_id!r}. "
            "Must be 1-63 chars, alphanumeric/hyphens/underscores, starting with alphanumeric."
        )


class ProjectWorkspace:
    """Manages isolated project directory trees under a shared root.

    Every filesystem operation resolves and checks the real path
    to prevent traversal attacks.
    """

    def __init__(self, projects_root: str | Path) -> None:
        self._root = Path(projects_root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    # ------------------------------------------------------------------
    # Project lifecycle
    # ------------------------------------------------------------------

    def create_project(self, project_id: str) -> Path:
        """Create a new project with all required subdirectories."""
        _validate_project_id(project_id)
        project_dir = self._root / project_id
        if project_dir.exists():
            raise WorkspaceError(f"Project {project_id!r} already exists.")
        project_dir.mkdir()
        for subdir in PROJECT_SUBDIRS:
            (project_dir / subdir).mkdir()
        return project_dir

    def project_exists(self, project_id: str) -> bool:
        _validate_project_id(project_id)
        return (self._root / project_id).is_dir()

    def list_projects(self) -> list[str]:
        """Return sorted list of project IDs."""
        return sorted(
            d.name for d in self._root.iterdir()
            if d.is_dir() and _PROJECT_ID_RE.match(d.name)
        )

    def get_project_root(self, project_id: str) -> Path:
        """Return the resolved root path for a project, or raise."""
        _validate_project_id(project_id)
        project_dir = (self._root / project_id).resolve()
        if not project_dir.is_dir():
            raise ProjectNotFoundError(f"Project {project_id!r} not found.")
        return project_dir

    def get_subdir(self, project_id: str, subdir: str) -> Path:
        """Return a resolved subdirectory path within a project."""
        project_dir = self.get_project_root(project_id)
        target = (project_dir / subdir).resolve()
        self._enforce_boundary(project_id, target)
        if not target.is_dir():
            raise WorkspaceError(f"Subdirectory {subdir!r} not found in project {project_id!r}.")
        return target

    # ------------------------------------------------------------------
    # Safe file operations
    # ------------------------------------------------------------------

    def resolve_path(self, project_id: str, relative_path: str) -> Path:
        """Resolve a relative path within a project, enforcing isolation."""
        project_dir = self.get_project_root(project_id)
        target = (project_dir / relative_path).resolve()
        self._enforce_boundary(project_id, target)
        return target

    def write_file(self, project_id: str, relative_path: str, content: bytes) -> Path:
        """Write a file within a project's directory tree."""
        target = self.resolve_path(project_id, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Re-check after mkdir in case parent creation escapes
        self._enforce_boundary(project_id, target.parent.resolve())
        target.write_bytes(content)
        # Post-write verification: confirm written file is still within boundary
        actual = target.resolve()
        try:
            actual.relative_to((self._root / project_id).resolve())
        except ValueError:
            actual.unlink(missing_ok=True)
            raise PathTraversalError("Access denied: path escapes project boundary.")
        return target

    def read_file(self, project_id: str, relative_path: str) -> bytes:
        """Read a file from within a project's directory tree."""
        target = self.resolve_path(project_id, relative_path)
        if not target.is_file():
            raise WorkspaceError("File not found in project.")
        return target.read_bytes()

    def list_files(self, project_id: str, subdir: str = "") -> list[str]:
        """List files in a project subdirectory, relative to project root."""
        project_dir = self.get_project_root(project_id)
        target = (project_dir / subdir).resolve() if subdir else project_dir
        self._enforce_boundary(project_id, target)
        if not target.is_dir():
            return []
        return sorted(
            str(f.relative_to(project_dir))
            for f in target.rglob("*")
            if f.is_file()
        )

    # ------------------------------------------------------------------
    # Boundary enforcement
    # ------------------------------------------------------------------

    def _enforce_boundary(self, project_id: str, resolved_path: Path) -> None:
        """Raise PathTraversalError if resolved_path escapes the project root."""
        project_dir = (self._root / project_id).resolve()
        try:
            resolved_path.relative_to(project_dir)
        except ValueError:
            logger.warning(
                "Path traversal blocked: resolved=%s, project_root=%s",
                resolved_path,
                project_dir,
            )
            raise PathTraversalError("Access denied: path escapes project boundary.")

    def get_project_info(self, project_id: str) -> dict[str, Any]:
        """Return project metadata summary."""
        project_dir = self.get_project_root(project_id)
        subdirs = {}
        for sd in PROJECT_SUBDIRS:
            sd_path = project_dir / sd
            if sd_path.is_dir():
                file_count = sum(1 for _ in sd_path.rglob("*") if _.is_file())
                subdirs[sd] = {"exists": True, "file_count": file_count}
            else:
                subdirs[sd] = {"exists": False, "file_count": 0}
        return {
            "project_id": project_id,
            "root": str(project_dir),
            "subdirs": subdirs,
        }
