"""Tests for P10-04: CI quality gates and repository standards.

AC-1: PRs require passing unit/integration tests, lint, and type checks.
AC-2: Schema/migration checks run automatically in CI.
AC-3: Branch protections require all checks before merge.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from scripts.check_ci_gates import (
    PROJECT_ROOT,
    check_golden_datasets,
    check_migration_files,
    check_no_secrets,
    check_required_files,
    check_test_naming,
)
from scripts.check_adr import check_adr_files


# ---------------------------------------------------------------------------
# AC-1: CI workflow and linting config exist
# ---------------------------------------------------------------------------

class TestCIInfrastructure:
    def test_github_workflow_exists(self):
        assert (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").is_file()

    def test_workflow_has_required_jobs(self):
        content = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "lint:" in content
        assert "test:" in content
        assert "type-check:" in content
        assert "schema-check:" in content

    def test_workflow_runs_on_pr(self):
        content = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "pull_request:" in content

    def test_workflow_runs_ruff(self):
        content = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "ruff check" in content
        assert "ruff format" in content

    def test_workflow_runs_pytest(self):
        content = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "pytest" in content

    def test_workflow_runs_adr_check(self):
        content = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "check_adr.py" in content

    def test_workflow_runs_ci_gates(self):
        content = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "check_ci_gates.py" in content

    def test_ruff_config_in_pyproject(self):
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        assert "[tool.ruff]" in content
        assert "[tool.ruff.lint]" in content

    def test_ruff_targets_python_311(self):
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        assert 'target-version = "py311"' in content

    def test_ruff_in_dev_dependencies(self):
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        assert "ruff" in content

    def test_workflow_has_type_check(self):
        content = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "pyright" in content or "mypy" in content

    def test_workflow_migration_check_is_real(self):
        """Migration check must not be a no-op (no 'or True')."""
        content = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "or True" not in content


# ---------------------------------------------------------------------------
# AC-2: Quality gate checks pass
# ---------------------------------------------------------------------------

class TestQualityGates:
    def test_required_files_pass(self):
        errors = check_required_files()
        assert errors == [], f"Missing files: {errors}"

    def test_test_naming_pass(self):
        errors = check_test_naming()
        assert errors == [], f"Test naming issues: {errors}"

    def test_no_secrets_pass(self):
        errors = check_no_secrets()
        assert errors == [], f"Secret scan issues: {errors}"

    def test_migration_files_pass(self):
        errors = check_migration_files()
        assert errors == [], f"Migration issues: {errors}"

    def test_golden_datasets_pass(self):
        errors = check_golden_datasets()
        assert errors == [], f"Golden dataset issues: {errors}"

    def test_adr_check_passes(self):
        errors = check_adr_files()
        assert errors == [], f"ADR issues: {errors}"

    def test_full_ci_gates_script_exits_zero(self):
        result = subprocess.run(
            [sys.executable, "scripts/check_ci_gates.py"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"CI gates failed:\n{result.stdout}\n{result.stderr}"


# ---------------------------------------------------------------------------
# AC-2: Schema/migration checks
# ---------------------------------------------------------------------------

class TestSchemaChecks:
    def test_alembic_ini_exists(self):
        assert (PROJECT_ROOT / "alembic.ini").is_file()

    def test_migrations_directory_exists(self):
        assert (PROJECT_ROOT / "migrations" / "versions").is_dir()

    def test_initial_migration_exists(self):
        assert (PROJECT_ROOT / "migrations" / "versions" / "001_initial_schema.py").is_file()

    def test_migration_has_upgrade_and_downgrade(self):
        content = (PROJECT_ROOT / "migrations" / "versions" / "001_initial_schema.py").read_text()
        assert "def upgrade()" in content
        assert "def downgrade()" in content

    def test_env_py_imports_models(self):
        content = (PROJECT_ROOT / "migrations" / "env.py").read_text()
        assert "from packages.shared.db.models import Base" in content


# ---------------------------------------------------------------------------
# AC-3: Repository standards
# ---------------------------------------------------------------------------

class TestRepositoryStandards:
    def test_pyproject_has_project_metadata(self):
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        assert "[project]" in content
        assert 'name = "quant-platform-mvp"' in content
        assert "requires-python" in content

    def test_pyproject_has_dependencies(self):
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        assert "fastapi" in content
        assert "sqlalchemy" in content
        assert "alembic" in content
        assert "pydantic" in content
        assert "numpy" in content
        assert "pandas" in content
        assert "scikit-learn" in content

    def test_pyproject_has_dev_dependencies(self):
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        assert "pytest" in content
        assert "ruff" in content

    def test_test_directory_structure(self):
        assert (PROJECT_ROOT / "tests" / "unit").is_dir()

    def test_packages_directory_structure(self):
        assert (PROJECT_ROOT / "packages" / "shared").is_dir()
        assert (PROJECT_ROOT / "packages" / "survey_analysis").is_dir()

    def test_docs_directory_structure(self):
        assert (PROJECT_ROOT / "docs" / "05_decisions").is_dir()
