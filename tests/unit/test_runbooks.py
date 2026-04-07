"""Tests for P10-06: Runbooks and onboarding playbooks.

AC-1: New engineer can set up and run core workflows using docs only.
AC-2: Operational runbooks cover common failure scenarios and recovery.
AC-3: Docs include ownership and escalation paths.
"""

from __future__ import annotations

from pathlib import Path

import pytest

OPS_DIR = Path(__file__).resolve().parents[2] / "docs" / "06_operations"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# AC-1: Onboarding playbook
# ---------------------------------------------------------------------------

class TestOnboardingPlaybook:
    def test_onboarding_file_exists(self):
        assert (OPS_DIR / "ONBOARDING.md").is_file()

    def test_covers_prerequisites(self):
        content = (OPS_DIR / "ONBOARDING.md").read_text()
        assert "Python 3.11" in content or "Python 3.12" in content

    def test_covers_clone_and_install(self):
        content = (OPS_DIR / "ONBOARDING.md").read_text()
        assert "git clone" in content
        assert "pip install" in content

    def test_covers_env_setup(self):
        content = (OPS_DIR / "ONBOARDING.md").read_text()
        assert ".env" in content
        assert "DATABASE_URL" in content

    def test_covers_database_init(self):
        content = (OPS_DIR / "ONBOARDING.md").read_text()
        assert "migration" in content.lower() or "run_upgrade" in content

    def test_covers_running_tests(self):
        content = (OPS_DIR / "ONBOARDING.md").read_text()
        assert "pytest" in content

    def test_covers_starting_server(self):
        content = (OPS_DIR / "ONBOARDING.md").read_text()
        assert "uvicorn" in content
        assert "8010" in content

    def test_covers_key_directories(self):
        content = (OPS_DIR / "ONBOARDING.md").read_text()
        assert "apps/api/" in content
        assert "packages/shared/" in content
        assert "packages/survey_analysis/" in content

    def test_covers_running_analysis(self):
        content = (OPS_DIR / "ONBOARDING.md").read_text()
        assert "execute_run" in content or "AnalysisRun" in content

    def test_env_example_exists(self):
        assert (PROJECT_ROOT / ".env.example").is_file()


# ---------------------------------------------------------------------------
# AC-2: Operational runbooks
# ---------------------------------------------------------------------------

class TestRunbooks:
    def test_runbooks_file_exists(self):
        assert (OPS_DIR / "RUNBOOKS.md").is_file()

    def test_covers_database_migration(self):
        content = (OPS_DIR / "RUNBOOKS.md").read_text()
        assert "Migration" in content
        assert "run_upgrade" in content
        assert "run_downgrade" in content

    def test_covers_backup_and_restore(self):
        content = (OPS_DIR / "RUNBOOKS.md").read_text()
        assert "Backup" in content
        assert "backup_sqlite" in content
        assert "restore" in content.lower()

    def test_covers_stuck_jobs(self):
        content = (OPS_DIR / "RUNBOOKS.md").read_text()
        assert "Stuck" in content or "stuck" in content
        assert "dead_letter" in content or "dead letter" in content.lower()

    def test_covers_api_server_issues(self):
        content = (OPS_DIR / "RUNBOOKS.md").read_text()
        assert "Server" in content
        assert "500" in content or "Internal Server Error" in content

    def test_covers_auth_failures(self):
        content = (OPS_DIR / "RUNBOOKS.md").read_text()
        assert "Authentication" in content
        assert "JWT" in content

    def test_covers_optimistic_locking(self):
        content = (OPS_DIR / "RUNBOOKS.md").read_text()
        assert "Optimistic" in content or "409" in content
        assert "version_token" in content

    def test_covers_analysis_failures(self):
        content = (OPS_DIR / "RUNBOOKS.md").read_text()
        assert "Analysis" in content
        assert "error_type" in content

    def test_covers_golden_dataset_drift(self):
        content = (OPS_DIR / "RUNBOOKS.md").read_text()
        assert "Golden" in content or "golden" in content
        assert "generator" in content

    def test_covers_ci_failures(self):
        content = (OPS_DIR / "RUNBOOKS.md").read_text()
        assert "CI" in content
        assert "ruff" in content

    def test_covers_disaster_recovery(self):
        content = (OPS_DIR / "RUNBOOKS.md").read_text()
        assert "Disaster" in content or "Recovery" in content
        assert "verify_integrity" in content

    def test_has_table_of_contents(self):
        content = (OPS_DIR / "RUNBOOKS.md").read_text()
        assert "Table of Contents" in content


# ---------------------------------------------------------------------------
# AC-3: Ownership and escalation
# ---------------------------------------------------------------------------

class TestOwnership:
    def test_ownership_file_exists(self):
        assert (OPS_DIR / "OWNERSHIP.md").is_file()

    def test_covers_component_ownership(self):
        content = (OPS_DIR / "OWNERSHIP.md").read_text()
        assert "Component" in content
        assert "Owner" in content
        assert "API Server" in content or "apps/api" in content

    def test_covers_severity_levels(self):
        content = (OPS_DIR / "OWNERSHIP.md").read_text()
        assert "P0" in content
        assert "P1" in content
        assert "Critical" in content

    def test_covers_escalation_procedure(self):
        content = (OPS_DIR / "OWNERSHIP.md").read_text()
        assert "Escalation" in content
        assert "Identify" in content
        assert "Diagnose" in content

    def test_covers_decision_authority(self):
        content = (OPS_DIR / "OWNERSHIP.md").read_text()
        assert "Decision" in content
        assert "ADR" in content

    def test_covers_key_contacts(self):
        content = (OPS_DIR / "OWNERSHIP.md").read_text()
        assert "Team Lead" in content or "Contact" in content

    def test_all_major_components_listed(self):
        content = (OPS_DIR / "OWNERSHIP.md").read_text()
        assert "auth" in content.lower()
        assert "database" in content.lower() or "db/" in content
        assert "analysis" in content.lower() or "drivers" in content.lower()
        assert "job" in content.lower() or "queue" in content.lower()
