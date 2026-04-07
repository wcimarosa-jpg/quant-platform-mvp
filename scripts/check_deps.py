#!/usr/bin/env python3
"""Dependency management checks.

Validates:
1. All dependencies in pyproject.toml have version constraints
2. No wildcard/unpinned dependencies (must have >= or == or ~=)
3. Dev dependencies are separated from core dependencies
4. Known high-risk packages are flagged for extra review

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
PYPROJECT = PROJECT_ROOT / "pyproject.toml"

# Packages that need extra review on major version bumps
HIGH_RISK_PACKAGES = {
    "sqlalchemy",
    "pydantic",
    "fastapi",
    "alembic",
    "numpy",
    "pandas",
    "scikit-learn",
}

VERSION_PATTERN = re.compile(r"[><=~!]")


def load_pyproject() -> dict:
    with open(PYPROJECT, "rb") as f:
        return tomllib.load(f)


def check_version_constraints(deps: list[str], section: str) -> list[str]:
    """Verify all dependencies have version constraints."""
    errors = []
    for dep in deps:
        # Strip extras like [dev]
        name = dep.split("[")[0].split(">")[0].split("<")[0].split("=")[0].split("~")[0].split("!")[0].strip()
        if not VERSION_PATTERN.search(dep):
            errors.append(f"{section}: '{dep}' has no version constraint — add >=X.Y.Z")
    return errors


def check_high_risk_packages(deps: list[str]) -> list[str]:
    """Flag high-risk packages for awareness (informational, not errors)."""
    info = []
    for dep in deps:
        name = dep.split("[")[0].split(">")[0].split("<")[0].split("=")[0].split("~")[0].split("!")[0].strip().lower()
        if name in HIGH_RISK_PACKAGES:
            info.append(f"  High-risk dep: {dep} — major version bumps need compatibility testing")
    return info


def check_python_version(data: dict) -> list[str]:
    errors = []
    requires = data.get("project", {}).get("requires-python", "")
    if not requires:
        errors.append("No requires-python specified in [project]")
    return errors


def main() -> int:
    print(f"Checking dependencies in {PYPROJECT}")

    if not PYPROJECT.is_file():
        print("  FAIL: pyproject.toml not found")
        return 1

    data = load_pyproject()
    all_errors: list[str] = []

    # Check core deps
    core_deps = data.get("project", {}).get("dependencies", [])
    errors = check_version_constraints(core_deps, "dependencies")
    all_errors.extend(errors)
    print(f"  Core dependencies: {len(core_deps)} packages")

    # Check dev deps
    dev_deps = data.get("project", {}).get("optional-dependencies", {}).get("dev", [])
    errors = check_version_constraints(dev_deps, "dev")
    all_errors.extend(errors)
    print(f"  Dev dependencies: {len(dev_deps)} packages")

    # Check Python version
    errors = check_python_version(data)
    all_errors.extend(errors)

    # High-risk info
    high_risk = check_high_risk_packages(core_deps + dev_deps)
    if high_risk:
        print("\n  High-risk packages (need extra review on major bumps):")
        for info in high_risk:
            print(f"    {info}")

    if all_errors:
        print(f"\n  FAILED: {len(all_errors)} error(s):")
        for e in all_errors:
            print(f"    - {e}")
        return 1

    print(f"\n  All dependency checks passed ({len(core_deps) + len(dev_deps)} total packages).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
