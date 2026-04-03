"""Section-level edit and regenerate workflow.

Supports targeted regeneration of individual sections within
a questionnaire, with change tracking and diff metadata.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import BaseModel, Field

from packages.shared.assistant_context import AssistantContext
from packages.shared.questionnaire_schema import Question, Questionnaire, Section


class SectionChange(BaseModel):
    """Describes what changed in a section regeneration."""

    change_id: str = Field(default_factory=lambda: f"chg-{uuid.uuid4().hex[:8]}")
    section_type: str
    action: str  # "regenerate", "edit"
    user_instruction: str
    explanation: str  # what changed and why
    questions_added: list[str] = Field(default_factory=list)
    questions_removed: list[str] = Field(default_factory=list)
    questions_modified: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))


class SectionDiff(BaseModel):
    """Diff between two versions of a section."""

    section_type: str
    before_question_count: int
    after_question_count: int
    added: list[str]     # question IDs added
    removed: list[str]   # question IDs removed
    modified: list[str]  # question IDs with changed text
    unchanged: list[str] # question IDs identical


class EditResult(BaseModel):
    """Result of a section edit/regenerate operation."""

    questionnaire_id: str
    section_type: str
    change: SectionChange
    diff: SectionDiff
    new_version: int
    sections_untouched: list[str]  # section types NOT modified


# ---------------------------------------------------------------------------
# Diff computation
# ---------------------------------------------------------------------------

def compute_section_diff(before: Section | None, after: Section) -> SectionDiff:
    """Compute the diff between two versions of a section."""
    if before is None:
        return SectionDiff(
            section_type=after.section_type,
            before_question_count=0,
            after_question_count=len(after.questions),
            added=[q.question_id for q in after.questions],
            removed=[],
            modified=[],
            unchanged=[],
        )

    before_map = {q.question_id: q for q in before.questions}
    after_map = {q.question_id: q for q in after.questions}

    before_ids = set(before_map.keys())
    after_ids = set(after_map.keys())

    added = sorted(after_ids - before_ids)
    removed = sorted(before_ids - after_ids)
    common = before_ids & after_ids

    modified = []
    unchanged = []
    for qid in sorted(common):
        if before_map[qid].question_text != after_map[qid].question_text:
            modified.append(qid)
        else:
            unchanged.append(qid)

    return SectionDiff(
        section_type=after.section_type,
        before_question_count=len(before.questions),
        after_question_count=len(after.questions),
        added=added,
        removed=removed,
        modified=modified,
        unchanged=unchanged,
    )


# ---------------------------------------------------------------------------
# Section regeneration
# ---------------------------------------------------------------------------

def regenerate_section(
    questionnaire: Questionnaire,
    section_type: str,
    user_instruction: str,
    ctx: AssistantContext,
    generator_fn: Callable[[AssistantContext, int], Section] | None = None,
) -> EditResult:
    """Regenerate a single section within a questionnaire.

    - Other sections remain untouched (AC-1)
    - Returns explanation of changes (AC-2)
    - Change is versioned with diff metadata (AC-3)

    Args:
        questionnaire: The current questionnaire to modify.
        section_type: Which section to regenerate.
        user_instruction: What the user wants changed.
        ctx: Current assistant context.
        generator_fn: Optional custom generator. If None, uses the default
                      engine generator for the section type.
    """
    # Find the target section
    old_section = questionnaire.get_section(section_type)
    if old_section is None:
        raise ValueError(f"Section {section_type!r} not found in questionnaire.")

    # Snapshot untouched sections
    untouched = [s.section_type for s in questionnaire.sections if s.section_type != section_type]

    # Generate replacement section
    if generator_fn:
        new_section = generator_fn(ctx, old_section.order)
    else:
        from packages.survey_generation.engine import _GENERATORS, _gen_placeholder
        gen = _GENERATORS.get(section_type)
        if gen:
            new_section = gen(ctx, old_section.order)
        else:
            new_section = _gen_placeholder(section_type, old_section.label, ctx, old_section.order)

    # Compute diff
    diff = compute_section_diff(old_section, new_section)

    # Build explanation grounded in the diff
    explanation = _build_explanation(section_type, user_instruction, diff)

    # Create change record
    change = SectionChange(
        section_type=section_type,
        action="regenerate",
        user_instruction=user_instruction,
        explanation=explanation,
        questions_added=diff.added,
        questions_removed=diff.removed,
        questions_modified=diff.modified,
    )

    # Replace the section in the questionnaire (AC-1: only this section changes)
    for i, s in enumerate(questionnaire.sections):
        if s.section_type == section_type:
            questionnaire.sections[i] = new_section
            break

    # Update questionnaire metadata
    questionnaire.version += 1
    questionnaire.total_questions = sum(len(s.questions) for s in questionnaire.sections)

    # Verify other sections untouched
    actual_untouched = [s.section_type for s in questionnaire.sections if s.section_type != section_type]
    if actual_untouched != untouched:
        raise RuntimeError("Other sections were unexpectedly modified during regeneration.")

    return EditResult(
        questionnaire_id=questionnaire.questionnaire_id,
        section_type=section_type,
        change=change,
        diff=diff,
        new_version=questionnaire.version,
        sections_untouched=untouched,
    )


def _build_explanation(section_type: str, user_instruction: str, diff: SectionDiff) -> str:
    """Build a human-readable explanation of what changed and why."""
    parts = [f"Regenerated the {section_type} section in response to: \"{user_instruction}\"."]

    if diff.added:
        parts.append(f"Added {len(diff.added)} new question(s): {', '.join(diff.added)}.")
    if diff.removed:
        parts.append(f"Removed {len(diff.removed)} question(s): {', '.join(diff.removed)}.")
    if diff.modified:
        parts.append(f"Modified {len(diff.modified)} question(s): {', '.join(diff.modified)}.")
    if diff.unchanged:
        parts.append(f"{len(diff.unchanged)} question(s) remained unchanged.")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Change history
# ---------------------------------------------------------------------------

class ChangeHistory:
    """Tracks all section changes for a questionnaire.

    TODO: Back with database for persistence across restarts.
    """

    def __init__(self) -> None:
        self._changes: dict[str, list[SectionChange]] = {}  # keyed by questionnaire_id

    def record(self, questionnaire_id: str, change: SectionChange) -> None:
        if questionnaire_id not in self._changes:
            self._changes[questionnaire_id] = []
        self._changes[questionnaire_id].append(change)

    def get_history(self, questionnaire_id: str) -> list[SectionChange]:
        return self._changes.get(questionnaire_id, [])

    def get_by_section(self, questionnaire_id: str, section_type: str) -> list[SectionChange]:
        return [
            c for c in self.get_history(questionnaire_id)
            if c.section_type == section_type
        ]
