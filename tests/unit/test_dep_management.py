"""Tests for P10-07: Dependency and upgrade management policy.

AC-1: Dependency update cadence is defined and automated.
AC-2: Security scanning runs in CI with actionable reporting.
AC-3: Upgrade checklist includes compatibility testing and rollback.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPS_DIR = PROJECT_ROOT / "docs" / "06_operations"

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


def _load_pyproject() -> dict:
    with open(PROJECT_ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)


# ---------------------------------------------------------------------------
# AC-1: Update cadence defined and automated
# ---------------------------------------------------------------------------

class TestUpdateCadence:
    def test_dependabot_config_exists(self):
        assert (PROJECT_ROOT / ".github" / "dependabot.yml").is_file()

    def test_dependabot_covers_pip(self):
        content = (PROJECT_ROOT / ".github" / "dependabot.yml").read_text()
        assert "pip" in content
        assert "weekly" in content

    def test_dependabot_covers_github_actions(self):
        content = (PROJECT_ROOT / ".github" / "dependabot.yml").read_text()
        assert "github-actions" in content

    def test_dependabot_has_pr_limits(self):
        content = (PROJECT_ROOT / ".github" / "dependabot.yml").read_text()
        assert "open-pull-requests-limit" in content

    def test_dependabot_groups_minor_patch(self):
        content = (PROJECT_ROOT / ".github" / "dependabot.yml").read_text()
        assert "minor" in content
        assert "patch" in content

    def test_dependency_management_doc_exists(self):
        assert (OPS_DIR / "DEPENDENCY_MANAGEMENT.md").is_file()

    def test_doc_defines_cadence(self):
        content = (OPS_DIR / "DEPENDENCY_MANAGEMENT.md").read_text()
        assert "Weekly" in content or "weekly" in content
        assert "Quarterly" in content or "quarterly" in content


# ---------------------------------------------------------------------------
# AC-2: Security scanning in CI
# ---------------------------------------------------------------------------

class TestSecurityScanning:
    def test_ci_has_security_scan_job(self):
        content = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "security-scan:" in content or "Security" in content

    def test_ci_runs_pip_audit(self):
        content = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "pip-audit" in content

    def test_ci_pip_audit_uses_strict(self):
        content = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "--strict" in content

    def test_ci_runs_dep_check(self):
        content = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "check_deps.py" in content

    def test_dep_check_script_exists(self):
        assert (PROJECT_ROOT / "scripts" / "check_deps.py").is_file()

    def test_dep_check_script_passes(self):
        result = subprocess.run(
            [sys.executable, "scripts/check_deps.py"],
            capture_output=True, text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"check_deps failed:\n{result.stdout}"

    def test_all_deps_have_version_constraints(self):
        data = _load_pyproject()
        core = data.get("project", {}).get("dependencies", [])
        dev = data.get("project", {}).get("optional-dependencies", {}).get("dev", [])
        for dep in core + dev:
            assert any(c in dep for c in [">=", "==", "~=", "<=", "!="]), \
                f"No version constraint: {dep}"

    def test_doc_covers_security_response(self):
        content = (OPS_DIR / "DEPENDENCY_MANAGEMENT.md").read_text()
        assert "Security" in content
        assert "CVE" in content or "vulnerability" in content.lower()


# ---------------------------------------------------------------------------
# AC-3: Upgrade checklist with rollback
# ---------------------------------------------------------------------------

class TestUpgradeChecklist:
    def test_doc_has_upgrade_checklist(self):
        content = (OPS_DIR / "DEPENDENCY_MANAGEMENT.md").read_text()
        assert "Upgrade Checklist" in content or "checklist" in content.lower()

    def test_checklist_covers_minor_updates(self):
        content = (OPS_DIR / "DEPENDENCY_MANAGEMENT.md").read_text()
        assert "Minor" in content or "minor" in content
        assert "Patch" in content or "patch" in content

    def test_checklist_covers_major_bumps(self):
        content = (OPS_DIR / "DEPENDENCY_MANAGEMENT.md").read_text()
        assert "Major" in content or "major" in content
        assert "migration guide" in content.lower() or "changelog" in content.lower()

    def test_checklist_references_golden_tests(self):
        content = (OPS_DIR / "DEPENDENCY_MANAGEMENT.md").read_text()
        assert "golden" in content.lower()

    def test_checklist_references_api_compat(self):
        content = (OPS_DIR / "DEPENDENCY_MANAGEMENT.md").read_text()
        assert "API" in content
        assert "compatibility" in content.lower() or "compat" in content.lower()

    def test_doc_has_rollback_procedure(self):
        content = (OPS_DIR / "DEPENDENCY_MANAGEMENT.md").read_text()
        assert "Rollback" in content
        assert "git revert" in content

    def test_doc_lists_high_risk_packages(self):
        content = (OPS_DIR / "DEPENDENCY_MANAGEMENT.md").read_text()
        assert "High-Risk" in content or "high-risk" in content
        assert "sqlalchemy" in content.lower()
        assert "pydantic" in content.lower()
        assert "numpy" in content.lower()

    def test_doc_has_version_constraint_policy(self):
        content = (OPS_DIR / "DEPENDENCY_MANAGEMENT.md").read_text()
        assert "Version Constraint" in content or "constraint" in content.lower()
        assert ">=" in content
