#!/usr/bin/env python3
"""CI check: validate Architecture Decision Records.

Verifies:
1. All ADR files follow naming convention (ADR-NNN-*.md)
2. Required sections present (Status, Date, Context, Decision, Consequences)
3. Sequential numbering (warnings for gaps)
4. Template and contributing docs exist

Exit code 0 = pass, 1 = failures found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ADR_DIR = Path(__file__).resolve().parents[1] / "docs" / "05_decisions"
ADR_PATTERN = re.compile(r"^ADR-(\d{3})-[\w-]+\.md$")
REQUIRED_SECTIONS = {"## Context", "## Decision", "## Consequences"}
REQUIRED_METADATA = {"**Status:**", "**Date:**"}
SKIP_FILES = {"ADR-TEMPLATE.md", "CONTRIBUTING.md"}


def check_adr_files() -> list[str]:
    """Return list of error messages. Empty = all checks pass."""
    errors: list[str] = []

    if not ADR_DIR.is_dir():
        errors.append(f"ADR directory not found: {ADR_DIR}")
        return errors

    # Check template and contributing exist
    if not (ADR_DIR / "ADR-TEMPLATE.md").is_file():
        errors.append("Missing ADR-TEMPLATE.md")
    if not (ADR_DIR / "CONTRIBUTING.md").is_file():
        errors.append("Missing CONTRIBUTING.md (contribution rules)")

    # Collect ADR files
    adr_files: dict[int, Path] = {}
    for f in sorted(ADR_DIR.glob("ADR-*.md")):
        if f.name in SKIP_FILES:
            continue
        match = ADR_PATTERN.match(f.name)
        if not match:
            errors.append(f"Bad naming: {f.name} (expected ADR-NNN-short-title.md)")
            continue
        num = int(match.group(1))
        adr_files[num] = f

    if not adr_files:
        errors.append("No ADR files found")
        return errors

    # Check sequential numbering (warnings only)
    nums = sorted(adr_files.keys())
    for i in range(len(nums) - 1):
        if nums[i + 1] - nums[i] > 1:
            print(f"  WARNING: Gap in ADR numbering between {nums[i]:03d} and {nums[i+1]:03d}")

    # Check each ADR for required content
    for num, path in sorted(adr_files.items()):
        content = path.read_text(encoding="utf-8")

        for meta in REQUIRED_METADATA:
            if meta not in content:
                errors.append(f"{path.name}: Missing metadata '{meta}'")

        for section in REQUIRED_SECTIONS:
            if section not in content:
                errors.append(f"{path.name}: Missing section '{section}'")

        # Check Status value is valid
        status_match = re.search(r"\*\*Status:\*\*\s*(\w[\w\s]*)", content)
        if status_match:
            status = status_match.group(1).strip()
            valid = {"Proposed", "Accepted", "Deprecated", "Superseded"}
            if not any(status.startswith(v) for v in valid):
                errors.append(f"{path.name}: Invalid status '{status}' (expected: {valid})")

    return errors


def main() -> int:
    print(f"Checking ADRs in {ADR_DIR}")
    errors = check_adr_files()

    if errors:
        print(f"\n  FAILED: {len(errors)} error(s):")
        for e in errors:
            print(f"    - {e}")
        return 1

    adr_count = len(list(ADR_DIR.glob("ADR-[0-9]*.md")))
    print(f"  OK: {adr_count} ADR(s) validated, template + rules present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
