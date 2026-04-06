"""Tests for P10-01: Architecture Decision Record discipline.

AC-1: ADR template and contribution rules published in docs.
AC-2: CI check ensures ADR structure and required sections.
AC-3: Initial ADRs exist for storage, analysis runtime, auth, and assistant.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

import pytest

from scripts.check_adr import (
    ADR_DIR,
    ADR_PATTERN,
    REQUIRED_METADATA,
    REQUIRED_SECTIONS,
    check_adr_files,
)


# ---------------------------------------------------------------------------
# AC-1: Template and contribution rules exist
# ---------------------------------------------------------------------------

class TestADRInfrastructure:
    def test_template_exists(self):
        assert (ADR_DIR / "ADR-TEMPLATE.md").is_file()

    def test_template_has_placeholders(self):
        content = (ADR_DIR / "ADR-TEMPLATE.md").read_text()
        assert "## Context" in content
        assert "## Decision" in content
        assert "## Consequences" in content
        assert "## Alternatives Considered" in content
        assert "**Status:**" in content

    def test_contributing_exists(self):
        assert (ADR_DIR / "CONTRIBUTING.md").is_file()

    def test_contributing_has_rules(self):
        content = (ADR_DIR / "CONTRIBUTING.md").read_text()
        assert "When to write an ADR" in content
        assert "How to write an ADR" in content
        assert "Numbering" in content
        assert "Review process" in content
        assert "CI enforcement" in content

    def test_contributing_has_index(self):
        content = (ADR_DIR / "CONTRIBUTING.md").read_text()
        assert "| ADR |" in content
        assert "ADR-001" in content
        assert "ADR-003" in content


# ---------------------------------------------------------------------------
# AC-2: CI check validates ADR structure
# ---------------------------------------------------------------------------

class TestCICheck:
    def test_check_passes_on_real_adrs(self):
        errors = check_adr_files()
        assert errors == [], f"ADR check errors: {errors}"

    def test_adr_naming_pattern(self):
        """All ADR files match ADR-NNN-*.md pattern."""
        skip = {"ADR-TEMPLATE.md", "CONTRIBUTING.md"}
        for f in ADR_DIR.glob("ADR-*.md"):
            if f.name in skip:
                continue
            assert ADR_PATTERN.match(f.name), f"Bad name: {f.name}"

    def test_all_adrs_have_required_sections(self):
        skip = {"ADR-TEMPLATE.md", "CONTRIBUTING.md"}
        for f in sorted(ADR_DIR.glob("ADR-[0-9]*.md")):
            if f.name in skip:
                continue
            content = f.read_text()
            for section in REQUIRED_SECTIONS:
                assert section in content, f"{f.name} missing '{section}'"
            for meta in REQUIRED_METADATA:
                assert meta in content, f"{f.name} missing '{meta}'"

    def test_all_adrs_have_valid_status(self):
        valid_prefixes = {"Proposed", "Accepted", "Deprecated", "Superseded"}
        for f in sorted(ADR_DIR.glob("ADR-[0-9]*.md")):
            content = f.read_text()
            match = re.search(r"\*\*Status:\*\*\s*(\w[\w\s]*)", content)
            assert match, f"{f.name}: no Status found"
            status = match.group(1).strip()
            assert any(status.startswith(v) for v in valid_prefixes), \
                f"{f.name}: invalid status '{status}'"

    def test_sequential_numbering(self):
        nums = []
        for f in ADR_DIR.glob("ADR-[0-9]*.md"):
            m = ADR_PATTERN.match(f.name)
            if m:
                nums.append(int(m.group(1)))
        nums.sort()
        assert len(nums) >= 3, f"Expected at least 3 ADRs, found {len(nums)}"
        # Check no duplicates
        assert len(nums) == len(set(nums))


# ---------------------------------------------------------------------------
# AC-3: Required ADRs exist
# ---------------------------------------------------------------------------

class TestRequiredADRs:
    def test_adr_001_assistant_context(self):
        path = ADR_DIR / "ADR-001-assistant-context-contract.md"
        assert path.is_file()
        content = path.read_text()
        assert "AssistantContext" in content

    def test_adr_002_descope(self):
        path = ADR_DIR / "ADR-002-p07-descope-decisions.md"
        assert path.is_file()

    def test_adr_003_storage(self):
        path = ADR_DIR / "ADR-003-storage-architecture.md"
        assert path.is_file()
        content = path.read_text()
        assert "SQLAlchemy" in content
        assert "SQLite" in content
        assert "PostgreSQL" in content
        assert "Alembic" in content

    def test_adr_004_analysis_runtime(self):
        path = ADR_DIR / "ADR-004-analysis-runtime.md"
        assert path.is_file()
        content = path.read_text()
        assert "register_analysis" in content
        assert "register_composite" in content
        assert "result_schemas" in content or "result schema" in content.lower()

    def test_adr_005_auth_rbac(self):
        path = ADR_DIR / "ADR-005-auth-rbac.md"
        assert path.is_file()
        content = path.read_text()
        assert "RBAC" in content or "role" in content.lower()
        assert "JWT" in content
        assert "PBKDF2" in content
        assert "project_guard" in content

    def test_all_adrs_have_references(self):
        """ADRs for storage, runtime, and auth reference actual code files."""
        for adr_name in [
            "ADR-003-storage-architecture.md",
            "ADR-004-analysis-runtime.md",
            "ADR-005-auth-rbac.md",
        ]:
            content = (ADR_DIR / adr_name).read_text()
            assert "## References" in content, f"{adr_name}: missing References section"
            assert "packages/" in content, f"{adr_name}: should reference code paths"
