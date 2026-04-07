#!/usr/bin/env python3
"""Release readiness checks.

Validates:
1. Version is consistent across pyproject.toml and main.py
2. CHANGELOG.md exists and has the current version or [Unreleased]
3. Release documentation files are present

Exit code 0 = pass, 1 = failures found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def get_pyproject_version() -> str:
    with open(PROJECT_ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def get_main_version() -> str | None:
    main_py = PROJECT_ROOT / "apps" / "api" / "main.py"
    content = main_py.read_text()
    match = re.search(r'version\s*=\s*"([^"]+)"', content)
    return match.group(1) if match else None


def check_version_sync() -> list[str]:
    errors = []
    pyproject_v = get_pyproject_version()
    main_v = get_main_version()

    if not main_v:
        errors.append("Could not find version in apps/api/main.py")
    elif pyproject_v != main_v:
        errors.append(f"Version mismatch: pyproject.toml={pyproject_v}, main.py={main_v}")

    return errors


def check_changelog() -> list[str]:
    errors = []
    changelog = PROJECT_ROOT / "CHANGELOG.md"
    if not changelog.is_file():
        errors.append("CHANGELOG.md not found at project root")
        return errors

    content = changelog.read_text()
    if "## [Unreleased]" not in content and "## [" not in content:
        errors.append("CHANGELOG.md has no version entries")

    pyproject_v = get_pyproject_version()
    if f"## [{pyproject_v}]" not in content and "## [Unreleased]" not in content:
        errors.append(f"CHANGELOG.md missing entry for current version {pyproject_v}")

    return errors


def check_release_files() -> list[str]:
    errors = []
    required = [
        "CHANGELOG.md",
        "docs/06_operations/RELEASE_PROCESS.md",
        "docs/06_operations/ROLLBACK_PROCEDURE.md",
    ]
    for f in required:
        if not (PROJECT_ROOT / f).is_file():
            errors.append(f"Missing release file: {f}")
    return errors


def main() -> int:
    print("Running release readiness checks...")
    all_errors: list[str] = []

    checks = [
        ("Version sync", check_version_sync),
        ("Changelog", check_changelog),
        ("Release files", check_release_files),
    ]

    for name, fn in checks:
        errors = fn()
        if errors:
            print(f"\n  FAIL: {name}")
            for e in errors:
                print(f"    - {e}")
        else:
            print(f"  OK: {name}")
        all_errors.extend(errors)

    version = get_pyproject_version()
    print(f"\n  Current version: {version}")

    if all_errors:
        print(f"\n  FAILED: {len(all_errors)} error(s)")
        return 1

    print("\n  All release checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
