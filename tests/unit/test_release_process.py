"""Tests for P10-08: Release process and rollback strategy.

AC-1: Release checklist is documented and used for each deploy.
AC-2: Semantic versioning and changelog process are enforced.
AC-3: Rollback procedure is validated in a drill and documented with timings.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPS_DIR = PROJECT_ROOT / "docs" / "06_operations"


# ---------------------------------------------------------------------------
# AC-1: Release checklist documented
# ---------------------------------------------------------------------------

class TestReleaseChecklist:
    def test_release_process_doc_exists(self):
        assert (OPS_DIR / "RELEASE_PROCESS.md").is_file()

    def test_has_pre_release_checklist(self):
        content = (OPS_DIR / "RELEASE_PROCESS.md").read_text()
        assert "Pre-Release" in content
        assert "- [ ]" in content  # checklist items

    def test_has_release_steps(self):
        content = (OPS_DIR / "RELEASE_PROCESS.md").read_text()
        assert "Release" in content
        assert "git tag" in content

    def test_has_post_release_steps(self):
        content = (OPS_DIR / "RELEASE_PROCESS.md").read_text()
        assert "Post-Release" in content

    def test_references_check_release_script(self):
        content = (OPS_DIR / "RELEASE_PROCESS.md").read_text()
        assert "check_release" in content

    def test_check_release_script_exists(self):
        assert (PROJECT_ROOT / "scripts" / "check_release.py").is_file()

    def test_check_release_script_passes(self):
        result = subprocess.run(
            [sys.executable, "scripts/check_release.py"],
            capture_output=True, text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"check_release failed:\n{result.stdout}"


# ---------------------------------------------------------------------------
# AC-2: Semantic versioning and changelog
# ---------------------------------------------------------------------------

class TestSemanticVersioning:
    def test_changelog_exists(self):
        assert (PROJECT_ROOT / "CHANGELOG.md").is_file()

    def test_changelog_follows_keepachangelog(self):
        content = (PROJECT_ROOT / "CHANGELOG.md").read_text()
        assert "Keep a Changelog" in content
        assert "Semantic Versioning" in content

    def test_changelog_has_unreleased_section(self):
        content = (PROJECT_ROOT / "CHANGELOG.md").read_text()
        assert "## [Unreleased]" in content

    def test_changelog_has_initial_release(self):
        content = (PROJECT_ROOT / "CHANGELOG.md").read_text()
        assert "## [0.1.0]" in content

    def test_version_in_pyproject_is_semver(self):
        from scripts.check_release import get_pyproject_version
        version = get_pyproject_version()
        parts = version.split(".")
        assert len(parts) == 3, f"Not semver: {version}"
        for p in parts:
            assert p.isdigit(), f"Non-numeric version part: {p}"

    def test_version_sync_pyproject_and_main(self):
        from scripts.check_release import get_pyproject_version, get_main_version
        assert get_pyproject_version() == get_main_version()

    def test_release_doc_explains_semver(self):
        content = (OPS_DIR / "RELEASE_PROCESS.md").read_text()
        assert "MAJOR" in content
        assert "MINOR" in content
        assert "PATCH" in content

    def test_release_doc_lists_version_locations(self):
        content = (OPS_DIR / "RELEASE_PROCESS.md").read_text()
        assert "pyproject.toml" in content
        assert "main.py" in content
        assert "CHANGELOG.md" in content

    def test_changelog_categories_present(self):
        content = (PROJECT_ROOT / "CHANGELOG.md").read_text()
        assert "### Added" in content


# ---------------------------------------------------------------------------
# AC-3: Rollback procedure validated with timings
# ---------------------------------------------------------------------------

class TestRollbackProcedure:
    def test_rollback_doc_exists(self):
        assert (OPS_DIR / "ROLLBACK_PROCEDURE.md").is_file()

    def test_has_timing_targets(self):
        content = (OPS_DIR / "ROLLBACK_PROCEDURE.md").read_text()
        assert "Timing" in content
        assert "< 5 min" in content or "<5 min" in content
        assert "< 30 min" in content or "<30 min" in content

    def test_has_numbered_steps(self):
        content = (OPS_DIR / "ROLLBACK_PROCEDURE.md").read_text()
        assert "Step 1" in content
        assert "Step 2" in content
        assert "Step 3" in content

    def test_covers_code_rollback(self):
        content = (OPS_DIR / "ROLLBACK_PROCEDURE.md").read_text()
        assert "git checkout" in content or "git tag" in content

    def test_covers_migration_rollback(self):
        content = (OPS_DIR / "ROLLBACK_PROCEDURE.md").read_text()
        assert "run_downgrade" in content

    def test_covers_database_restore(self):
        content = (OPS_DIR / "ROLLBACK_PROCEDURE.md").read_text()
        assert "restore_sqlite" in content or "restore" in content.lower()
        assert "verify_integrity" in content

    def test_covers_smoke_test(self):
        content = (OPS_DIR / "ROLLBACK_PROCEDURE.md").read_text()
        assert "Smoke" in content or "smoke" in content
        assert "pytest" in content

    def test_covers_communication(self):
        content = (OPS_DIR / "ROLLBACK_PROCEDURE.md").read_text()
        assert "Communicate" in content or "team" in content.lower()

    def test_references_recovery_drill_tests(self):
        content = (OPS_DIR / "ROLLBACK_PROCEDURE.md").read_text()
        assert "test_migrations_backup" in content or "RecoveryDrill" in content

    def test_has_drill_schedule(self):
        content = (OPS_DIR / "ROLLBACK_PROCEDURE.md").read_text()
        assert "Drill" in content
        assert "quarterly" in content.lower() or "schedule" in content.lower()

    def test_has_pre_release_backup_checklist(self):
        content = (OPS_DIR / "ROLLBACK_PROCEDURE.md").read_text()
        assert "Pre-Release Backup" in content or "backup" in content.lower()
