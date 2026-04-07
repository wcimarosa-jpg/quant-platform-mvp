#!/usr/bin/env python3
"""CI quality gates — validates repository standards.

Checks:
1. Required files exist (pyproject.toml, alembic.ini, CI workflow, etc.)
2. All test files follow naming conventions
3. No secrets or credentials in tracked files
4. Migration files are valid Python
5. Golden datasets exist for registered methodologies

Exit code 0 = pass, 1 = failures found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def check_required_files() -> list[str]:
    """Verify required repo files exist."""
    errors = []
    required = [
        "pyproject.toml",
        "alembic.ini",
        ".github/workflows/ci.yml",
        "scripts/check_adr.py",
        "scripts/check_ci_gates.py",
        "migrations/env.py",
        "migrations/versions/001_initial_schema.py",
        "packages/shared/db/models.py",
        "packages/shared/db/engine.py",
    ]
    for f in required:
        if not (PROJECT_ROOT / f).is_file():
            errors.append(f"Missing required file: {f}")
    return errors


def check_test_naming() -> list[str]:
    """Verify test files follow test_*.py naming convention."""
    errors = []
    test_dir = PROJECT_ROOT / "tests"
    if not test_dir.is_dir():
        return ["tests/ directory not found"]

    for py_file in test_dir.rglob("*.py"):
        if py_file.name == "__init__.py" or py_file.name == "conftest.py":
            continue
        if not py_file.name.startswith("test_"):
            errors.append(f"Test file not prefixed with test_: {py_file.relative_to(PROJECT_ROOT)}")
    return errors


def check_no_secrets() -> list[str]:
    """Scan for common secret patterns in Python files."""
    errors = []
    secret_patterns = [
        (re.compile(r'(?:password|secret|api_key|token)\s*=\s*["\'][^"\']{8,}["\']', re.IGNORECASE),
         "Possible hardcoded secret"),
    ]
    skip_dirs = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache"}
    skip_files = {"check_ci_gates.py"}  # this file contains the patterns as regex

    for py_file in PROJECT_ROOT.rglob("*.py"):
        if any(d in py_file.parts for d in skip_dirs):
            continue
        if py_file.name in skip_files:
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pattern, desc in secret_patterns:
            matches = pattern.findall(content)
            for match in matches:
                # Allow known safe patterns
                if any(safe in match.lower() for safe in [
                    "dev-secret", "replace_me", "change-in-production",
                    "test", "example", "dummy", "fixture", "sha256:",
                ]):
                    continue
                errors.append(f"{desc} in {py_file.relative_to(PROJECT_ROOT)}: {match[:60]}...")
    return errors


def check_migration_files() -> list[str]:
    """Verify migration files are valid Python."""
    errors = []
    versions_dir = PROJECT_ROOT / "migrations" / "versions"
    if not versions_dir.is_dir():
        return ["migrations/versions/ directory not found"]

    for py_file in versions_dir.glob("*.py"):
        if py_file.name == "__init__.py":
            continue
        try:
            compile(py_file.read_text(encoding="utf-8"), str(py_file), "exec")
        except SyntaxError as e:
            errors.append(f"Migration syntax error in {py_file.name}: {e}")
    return errors


def check_golden_datasets() -> list[str]:
    """Verify golden datasets exist for each methodology."""
    errors = []
    golden_dir = PROJECT_ROOT / "data" / "fixtures" / "golden"
    expected_files = [
        "drivers_expected.json",
        "maxdiff_turf_expected.json",
        "segmentation_expected.json",
        "generator.py",
    ]
    for f in expected_files:
        if not (golden_dir / f).is_file():
            errors.append(f"Missing golden dataset: {f}")
    return errors


def main() -> int:
    print("Running CI quality gates...")
    all_errors: list[str] = []

    checks = [
        ("Required files", check_required_files),
        ("Test naming", check_test_naming),
        ("Secret scan", check_no_secrets),
        ("Migration syntax", check_migration_files),
        ("Golden datasets", check_golden_datasets),
    ]

    for name, check_fn in checks:
        errors = check_fn()
        if errors:
            print(f"\n  FAIL: {name} ({len(errors)} error(s))")
            for e in errors:
                print(f"    - {e}")
        else:
            print(f"  OK: {name}")
        all_errors.extend(errors)

    if all_errors:
        print(f"\n  FAILED: {len(all_errors)} total error(s)")
        return 1

    print("\n  All CI quality gates passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
