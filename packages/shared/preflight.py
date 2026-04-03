"""Generation preflight gate.

Blocks questionnaire generation until minimum brief context is complete.
Returns structured check results with targeted prompts for missing items.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .assistant_context import Methodology
from .brief_parser import BriefFields


class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"


class PreflightCheck(BaseModel):
    """One preflight check result."""

    check_id: str
    label: str
    status: CheckStatus
    message: str
    assistant_prompt: str | None = None  # targeted prompt to fix this


class PreflightResult(BaseModel):
    """Complete preflight gate result."""

    can_generate: bool
    checks: list[PreflightCheck]
    blocking_count: int
    warning_count: int

    def blocking_checks(self) -> list[PreflightCheck]:
        return [c for c in self.checks if c.status == CheckStatus.FAIL]

    def warning_checks(self) -> list[PreflightCheck]:
        return [c for c in self.checks if c.status == CheckStatus.WARN]

    def for_ui(self) -> list[dict[str, Any]]:
        """Return structured data for UI display."""
        return [
            {
                "check_id": c.check_id,
                "label": c.label,
                "status": c.status.value,
                "message": c.message,
                "assistant_prompt": c.assistant_prompt,
            }
            for c in self.checks
        ]


# ---------------------------------------------------------------------------
# Check definitions
# ---------------------------------------------------------------------------

_REQUIRED_FIELD_PROMPTS: dict[str, dict[str, str]] = {
    "objectives": {
        "label": "Research Objectives",
        "prompt": "What are the main research questions this study should answer? What decisions will the findings inform?",
    },
    "audience": {
        "label": "Target Audience",
        "prompt": "Who should be surveyed? Describe the target respondents (demographics, behaviors, qualifications).",
    },
    "category": {
        "label": "Product Category",
        "prompt": "What product category or industry does this study focus on?",
    },
    "geography": {
        "label": "Geographic Scope",
        "prompt": "What markets or regions should this study cover? (e.g., US nationally representative, UK + Germany)",
    },
}

_OPTIONAL_FIELD_PROMPTS: dict[str, dict[str, str]] = {
    "constraints": {
        "label": "Constraints & Requirements",
        "prompt": "Are there any constraints? (LOI target, budget, language requirements, specific platforms)",
    },
}


def run_preflight(
    fields: BriefFields,
    methodology: Methodology | None = None,
) -> PreflightResult:
    """Run all preflight checks against a parsed brief.

    Returns a PreflightResult indicating whether generation can proceed.
    """
    checks: list[PreflightCheck] = []

    # Required field checks (blocking)
    for field_name, meta in _REQUIRED_FIELD_PROMPTS.items():
        value = getattr(fields, field_name, None)
        if value and len(value.strip()) > 0:
            checks.append(PreflightCheck(
                check_id=f"field_{field_name}",
                label=meta["label"],
                status=CheckStatus.PASS,
                message=f"{meta['label']} is provided.",
            ))
        else:
            checks.append(PreflightCheck(
                check_id=f"field_{field_name}",
                label=meta["label"],
                status=CheckStatus.FAIL,
                message=f"{meta['label']} is required but not provided.",
                assistant_prompt=meta["prompt"],
            ))

    # Optional field checks (warnings)
    for field_name, meta in _OPTIONAL_FIELD_PROMPTS.items():
        value = getattr(fields, field_name, None)
        if value and len(value.strip()) > 0:
            checks.append(PreflightCheck(
                check_id=f"field_{field_name}",
                label=meta["label"],
                status=CheckStatus.PASS,
                message=f"{meta['label']} is provided.",
            ))
        else:
            checks.append(PreflightCheck(
                check_id=f"field_{field_name}",
                label=meta["label"],
                status=CheckStatus.WARN,
                message=f"{meta['label']} is not specified. Defaults will be used.",
                assistant_prompt=meta["prompt"],
            ))

    # Methodology check
    if methodology:
        checks.append(PreflightCheck(
            check_id="methodology_selected",
            label="Methodology",
            status=CheckStatus.PASS,
            message=f"Methodology selected: {methodology.value}",
        ))
    else:
        checks.append(PreflightCheck(
            check_id="methodology_selected",
            label="Methodology",
            status=CheckStatus.FAIL,
            message="No methodology selected. Choose a methodology before generating.",
            assistant_prompt="What type of study is this? (e.g., Segmentation, A&U, Concept Test, Drivers, MaxDiff, Brand Tracker, TURF, Pricing)",
        ))

    # Brief content quality check
    if fields.raw_text and len(fields.raw_text.strip()) >= 50:
        checks.append(PreflightCheck(
            check_id="brief_content",
            label="Brief Content",
            status=CheckStatus.PASS,
            message="Brief has sufficient content for generation.",
        ))
    elif fields.raw_text and len(fields.raw_text.strip()) > 0:
        checks.append(PreflightCheck(
            check_id="brief_content",
            label="Brief Content",
            status=CheckStatus.WARN,
            message="Brief content is very short. Generation quality may be limited.",
            assistant_prompt="Can you provide more detail about this study? More context helps generate better questions.",
        ))
    else:
        checks.append(PreflightCheck(
            check_id="brief_content",
            label="Brief Content",
            status=CheckStatus.FAIL,
            message="No brief content available. Upload or enter a research brief first.",
            assistant_prompt="Upload a research brief document or describe your study objectives.",
        ))

    blocking = [c for c in checks if c.status == CheckStatus.FAIL]
    warnings = [c for c in checks if c.status == CheckStatus.WARN]

    return PreflightResult(
        can_generate=len(blocking) == 0,
        checks=checks,
        blocking_count=len(blocking),
        warning_count=len(warnings),
    )
