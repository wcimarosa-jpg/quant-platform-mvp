"""Questionnaire versioning and compare view.

Persists numbered versions, computes section-level diffs between
any two versions, and supports revert/fork operations.
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from packages.shared.questionnaire_schema import Questionnaire, Section
from packages.survey_generation.section_editor import SectionDiff, compute_section_diff


class VersionEntry(BaseModel):
    """One persisted questionnaire version."""

    version: int
    questionnaire: Questionnaire
    author: str  # "user", "assistant", or specific ID
    message: str  # commit-style message
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    parent_version: int | None = None  # for forks


class VersionComparison(BaseModel):
    """Section-level diff between two questionnaire versions."""

    base_version: int
    compare_version: int
    sections_added: list[str]    # section types in compare but not in base
    sections_removed: list[str]  # section types in base but not in compare
    sections_changed: list[SectionDiff]  # sections present in both but different
    sections_unchanged: list[str]  # identical sections


def _validate_unique_section_types(qre: Questionnaire) -> None:
    types = [s.section_type for s in qre.sections]
    if len(types) != len(set(types)):
        dupes = [t for t in types if types.count(t) > 1]
        raise ValueError(f"Duplicate section_type(s) in questionnaire: {set(dupes)}")


def compare_versions(base: Questionnaire, compare: Questionnaire) -> VersionComparison:
    """Compute section-level diff between two questionnaire versions."""
    _validate_unique_section_types(base)
    _validate_unique_section_types(compare)
    base_map = {s.section_type: s for s in base.sections}
    compare_map = {s.section_type: s for s in compare.sections}

    base_types = set(base_map.keys())
    compare_types = set(compare_map.keys())

    added = sorted(compare_types - base_types)
    removed = sorted(base_types - compare_types)

    changed: list[SectionDiff] = []
    unchanged: list[str] = []

    for st in sorted(base_types & compare_types):
        diff = compute_section_diff(base_map[st], compare_map[st])
        if diff.added or diff.removed or diff.modified:
            changed.append(diff)
        else:
            unchanged.append(st)

    return VersionComparison(
        base_version=base.version,
        compare_version=compare.version,
        sections_added=added,
        sections_removed=removed,
        sections_changed=changed,
        sections_unchanged=unchanged,
    )


class VersionStore:
    """Persists questionnaire versions with optional file-backed storage.

    When ``persist_path`` is provided, all versions are saved to disk
    as JSON and loaded on init, surviving restarts.
    """

    def __init__(self, persist_path: str | Path | None = None) -> None:
        self._versions: dict[str, list[VersionEntry]] = {}
        self._persist_path = Path(persist_path) if persist_path else None
        if self._persist_path and self._persist_path.exists():
            self._load()

    def _save(self) -> None:
        if not self._persist_path:
            return
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, list[dict]] = {}
        for qid, entries in self._versions.items():
            data[qid] = [e.model_dump(mode="json") for e in entries]
        self._persist_path.write_text(json.dumps(data, default=str), encoding="utf-8")

    def _load(self) -> None:
        if not self._persist_path or not self._persist_path.exists():
            return
        raw = json.loads(self._persist_path.read_text(encoding="utf-8"))
        for qid, entries in raw.items():
            self._versions[qid] = [VersionEntry.model_validate(e) for e in entries]

    def save_version(
        self,
        questionnaire: Questionnaire,
        author: str,
        message: str,
        parent_version: int | None = None,
    ) -> VersionEntry:
        """Save the current questionnaire state as a new version."""
        qid = questionnaire.questionnaire_id
        snapshot = questionnaire.model_copy(deep=True)

        entry = VersionEntry(
            version=snapshot.version,
            questionnaire=snapshot,
            author=author,
            message=message,
            parent_version=parent_version,
        )

        if qid not in self._versions:
            self._versions[qid] = []
        self._versions[qid].append(entry)
        self._save()
        return entry

    def get_version(self, questionnaire_id: str, version: int) -> VersionEntry | None:
        """Retrieve a specific version."""
        for entry in self._versions.get(questionnaire_id, []):
            if entry.version == version:
                return entry
        return None

    def get_latest(self, questionnaire_id: str) -> VersionEntry | None:
        """Get the most recent version."""
        entries = self._versions.get(questionnaire_id, [])
        return entries[-1] if entries else None

    def list_versions(self, questionnaire_id: str) -> list[dict[str, Any]]:
        """Return summary of all versions for a questionnaire."""
        return [
            {
                "version": e.version,
                "author": e.author,
                "message": e.message,
                "created_at": e.created_at.isoformat(),
                "parent_version": e.parent_version,
                "section_count": len(e.questionnaire.sections),
                "question_count": e.questionnaire.total_questions,
            }
            for e in self._versions.get(questionnaire_id, [])
        ]

    def compare(self, questionnaire_id: str, base_version: int, compare_version: int) -> VersionComparison:
        """Compare two versions of a questionnaire."""
        base = self.get_version(questionnaire_id, base_version)
        if not base:
            raise ValueError(f"Version {base_version} not found for {questionnaire_id}")
        compare = self.get_version(questionnaire_id, compare_version)
        if not compare:
            raise ValueError(f"Version {compare_version} not found for {questionnaire_id}")
        return compare_versions(base.questionnaire, compare.questionnaire)

    def revert(self, questionnaire_id: str, target_version: int, author: str = "user") -> Questionnaire:
        """Revert to a prior version, creating a new version with incremented number.

        Returns a deep copy of the target version's questionnaire with
        version number set to latest + 1.
        """
        target = self.get_version(questionnaire_id, target_version)
        if not target:
            raise ValueError(f"Version {target_version} not found for {questionnaire_id}")

        latest = self.get_latest(questionnaire_id)
        new_version_num = (latest.version if latest else 0) + 1

        reverted = target.questionnaire.model_copy(deep=True)
        reverted.version = new_version_num

        self.save_version(
            reverted,
            author=author,
            message=f"Reverted to version {target_version}",
            parent_version=target_version,
        )

        return reverted

    def fork(self, questionnaire_id: str, source_version: int, new_project_id: str | None = None) -> Questionnaire:
        """Fork from a prior version, creating a new v1 questionnaire.

        Optionally assigns to a different project.
        """
        source = self.get_version(questionnaire_id, source_version)
        if not source:
            raise ValueError(f"Version {source_version} not found for {questionnaire_id}")

        forked = source.questionnaire.model_copy(deep=True)
        forked.questionnaire_id = f"qre-{uuid.uuid4().hex[:8]}"
        forked.version = 1
        if new_project_id:
            forked.project_id = new_project_id

        self.save_version(
            forked,
            author="user",
            message=f"Forked from {questionnaire_id} v{source_version}",
            parent_version=source_version,
        )

        return forked

    @property
    def count(self) -> int:
        return sum(len(v) for v in self._versions.values())
