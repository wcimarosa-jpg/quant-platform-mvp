"""Contract tests for project workspace isolation (P01-02).

AC-1: Project folders created: Briefs, Questionnaires, Data, Mappings, Runs, Outputs, Logs.
AC-2: Cross-project read/write is rejected at service boundary.
AC-3: Isolation tests cover malicious path traversal attempts.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from packages.shared.workspace import (
    PROJECT_SUBDIRS,
    InvalidProjectIdError,
    PathTraversalError,
    ProjectNotFoundError,
    ProjectWorkspace,
    WorkspaceError,
)


@pytest.fixture
def ws(tmp_path: Path) -> ProjectWorkspace:
    return ProjectWorkspace(tmp_path / "projects")


@pytest.fixture
def ws_with_project(ws: ProjectWorkspace) -> ProjectWorkspace:
    ws.create_project("test-project")
    return ws


# ---------------------------------------------------------------------------
# AC-1: Project folders created
# ---------------------------------------------------------------------------

REQUIRED_SUBDIRS = [
    "Briefs",
    "Questionnaires",
    "Data",
    "Mappings",
    "Runs",
    "Outputs",
    "Logs",
]


class TestProjectCreation:
    def test_create_project_returns_path(self, ws: ProjectWorkspace):
        path = ws.create_project("my-project")
        assert path.is_dir()

    def test_all_required_subdirs_created(self, ws: ProjectWorkspace):
        ws.create_project("proj-001")
        project_dir = ws.get_project_root("proj-001")
        for subdir in REQUIRED_SUBDIRS:
            assert (project_dir / subdir).is_dir(), f"Missing subdir: {subdir}"

    def test_subdirs_match_constant(self):
        assert set(REQUIRED_SUBDIRS) == set(PROJECT_SUBDIRS)

    def test_duplicate_project_raises(self, ws: ProjectWorkspace):
        ws.create_project("dup-test")
        with pytest.raises(WorkspaceError, match="already exists"):
            ws.create_project("dup-test")

    def test_project_exists(self, ws_with_project: ProjectWorkspace):
        assert ws_with_project.project_exists("test-project") is True
        assert ws_with_project.project_exists("nonexistent") is False

    def test_list_projects(self, ws: ProjectWorkspace):
        ws.create_project("alpha")
        ws.create_project("beta")
        ws.create_project("gamma")
        assert ws.list_projects() == ["alpha", "beta", "gamma"]

    def test_get_project_info(self, ws_with_project: ProjectWorkspace):
        info = ws_with_project.get_project_info("test-project")
        assert info["project_id"] == "test-project"
        assert len(info["subdirs"]) == 7
        for sd in REQUIRED_SUBDIRS:
            assert info["subdirs"][sd]["exists"] is True

    def test_get_subdir(self, ws_with_project: ProjectWorkspace):
        briefs_dir = ws_with_project.get_subdir("test-project", "Briefs")
        assert briefs_dir.is_dir()
        assert briefs_dir.name == "Briefs"


# ---------------------------------------------------------------------------
# AC-1 + AC-2: File operations within a project
# ---------------------------------------------------------------------------

class TestFileOperations:
    def test_write_and_read_file(self, ws_with_project: ProjectWorkspace):
        content = b"Hello, research brief!"
        ws_with_project.write_file("test-project", "Briefs/brief.md", content)
        result = ws_with_project.read_file("test-project", "Briefs/brief.md")
        assert result == content

    def test_write_creates_nested_dirs(self, ws_with_project: ProjectWorkspace):
        ws_with_project.write_file(
            "test-project", "Runs/run-001/output.csv", b"col1,col2\n"
        )
        result = ws_with_project.read_file("test-project", "Runs/run-001/output.csv")
        assert result == b"col1,col2\n"

    def test_read_nonexistent_file_raises(self, ws_with_project: ProjectWorkspace):
        with pytest.raises(WorkspaceError, match="File not found"):
            ws_with_project.read_file("test-project", "Briefs/nope.md")

    def test_error_messages_do_not_leak_paths(self, ws_with_project: ProjectWorkspace):
        """Verify traversal errors use generic messages, not internal paths."""
        with pytest.raises(PathTraversalError) as exc_info:
            ws_with_project.resolve_path("test-project", "../../etc/passwd")
        msg = str(exc_info.value)
        assert "Access denied" in msg
        # Should NOT contain the actual resolved path
        assert "etc" not in msg.lower() or "passwd" not in msg.lower()

    def test_list_files(self, ws_with_project: ProjectWorkspace):
        ws_with_project.write_file("test-project", "Briefs/a.md", b"a")
        ws_with_project.write_file("test-project", "Briefs/b.md", b"b")
        ws_with_project.write_file("test-project", "Data/file.csv", b"csv")
        files = ws_with_project.list_files("test-project", "Briefs")
        assert len(files) == 2
        all_files = ws_with_project.list_files("test-project")
        assert len(all_files) == 3

    def test_list_files_empty_subdir(self, ws_with_project: ProjectWorkspace):
        files = ws_with_project.list_files("test-project", "Outputs")
        assert files == []


# ---------------------------------------------------------------------------
# AC-2: Cross-project isolation
# ---------------------------------------------------------------------------

class TestCrossProjectIsolation:
    def test_cannot_read_other_project_via_relative_path(self, ws: ProjectWorkspace):
        ws.create_project("project-a")
        ws.create_project("project-b")
        ws.write_file("project-a", "Briefs/secret.md", b"classified")
        with pytest.raises(PathTraversalError):
            ws.read_file("project-b", "../project-a/Briefs/secret.md")

    def test_cannot_write_to_other_project(self, ws: ProjectWorkspace):
        ws.create_project("project-a")
        ws.create_project("project-b")
        with pytest.raises(PathTraversalError):
            ws.write_file("project-b", "../project-a/Briefs/injected.md", b"evil")

    def test_cannot_list_other_project_files(self, ws: ProjectWorkspace):
        ws.create_project("project-a")
        ws.create_project("project-b")
        ws.write_file("project-a", "Data/data.csv", b"data")
        with pytest.raises(PathTraversalError):
            ws.list_files("project-b", "../project-a/Data")

    def test_resolve_path_rejects_cross_project(self, ws: ProjectWorkspace):
        ws.create_project("project-a")
        ws.create_project("project-b")
        with pytest.raises(PathTraversalError):
            ws.resolve_path("project-b", "../project-a/anything")


# ---------------------------------------------------------------------------
# AC-3: Path traversal attack vectors
# ---------------------------------------------------------------------------

class TestPathTraversalAttacks:
    def test_dotdot_escape(self, ws_with_project: ProjectWorkspace):
        with pytest.raises(PathTraversalError):
            ws_with_project.resolve_path("test-project", "../../etc/passwd")

    def test_deep_dotdot_escape(self, ws_with_project: ProjectWorkspace):
        with pytest.raises(PathTraversalError):
            ws_with_project.resolve_path(
                "test-project", "Briefs/../../../../etc/shadow"
            )

    def test_absolute_path_injection(self, ws_with_project: ProjectWorkspace):
        # On Windows, an absolute path like C:\... or /tmp/... should be caught
        if os.name == "nt":
            attack = "C:\\Windows\\System32\\config\\SAM"
        else:
            attack = "/etc/passwd"
        with pytest.raises(PathTraversalError):
            ws_with_project.resolve_path("test-project", attack)

    def test_null_byte_in_path(self, ws_with_project: ProjectWorkspace):
        with pytest.raises((PathTraversalError, ValueError, OSError)):
            ws_with_project.resolve_path("test-project", "Briefs/file\x00.md")

    def test_dotdot_with_backslash(self, ws_with_project: ProjectWorkspace):
        with pytest.raises(PathTraversalError):
            ws_with_project.resolve_path("test-project", "Briefs\\..\\..\\..\\etc\\passwd")

    def test_encoded_dotdot(self, ws_with_project: ProjectWorkspace):
        # URL-encoded traversal shouldn't work since we use Path.resolve()
        # The literal string "..%2f" becomes a directory name, not traversal
        path = ws_with_project.resolve_path("test-project", "Briefs/..%2f..%2f")
        # Should resolve inside the project (as a literal dir name)
        project_root = ws_with_project.get_project_root("test-project")
        assert str(path).startswith(str(project_root))

    def test_symlink_escape(self, ws_with_project: ProjectWorkspace, tmp_path: Path):
        """Symlink inside project pointing outside should be caught on resolve.
        NOTE: Skipped on Windows without dev mode. Must run in Linux CI."""
        project_root = ws_with_project.get_project_root("test-project")
        outside_file = tmp_path / "outside_secret.txt"
        outside_file.write_text("secret data")
        link_path = project_root / "Briefs" / "sneaky_link"
        try:
            link_path.symlink_to(outside_file)
        except OSError:
            pytest.skip("Symlink creation not permitted (Windows without dev mode)")
        with pytest.raises(PathTraversalError):
            ws_with_project.read_file("test-project", "Briefs/sneaky_link")

    def test_get_subdir_traversal(self, ws_with_project: ProjectWorkspace):
        with pytest.raises(PathTraversalError):
            ws_with_project.get_subdir("test-project", "../../../etc")


# ---------------------------------------------------------------------------
# Project ID validation
# ---------------------------------------------------------------------------

class TestProjectIdValidation:
    @pytest.mark.parametrize("bad_id", [
        "",
        " ",
        "../escape",
        "has spaces",
        ".hidden",
        "-starts-with-dash",
        "a" * 64,  # too long
        "has/slash",
        "has\\backslash",
    ])
    def test_invalid_project_ids_rejected(self, ws: ProjectWorkspace, bad_id: str):
        with pytest.raises(InvalidProjectIdError):
            ws.create_project(bad_id)

    @pytest.mark.parametrize("good_id", [
        "a",
        "project-123",
        "Client_Study_2026",
        "P01",
        "a" * 63,
    ])
    def test_valid_project_ids_accepted(self, ws: ProjectWorkspace, good_id: str):
        path = ws.create_project(good_id)
        assert path.is_dir()

    def test_nonexistent_project_raises(self, ws: ProjectWorkspace):
        with pytest.raises(ProjectNotFoundError):
            ws.get_project_root("no-such-project")
