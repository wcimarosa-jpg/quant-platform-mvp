"""Auto-mapping engine with editable, versioned mappings.

Maps data columns to questionnaire variables using multi-strategy
matching. Users can edit mappings, and each version is linked to
the questionnaire version and data file hash.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .data_profiler import ColumnProfile, DataProfile
from .questionnaire_schema import Question, Questionnaire, QuestionType


class MatchConfidence(str, Enum):
    HIGH = "high"       # >= 0.8
    MEDIUM = "medium"   # >= 0.5
    LOW = "low"         # >= 0.3
    NONE = "none"       # < 0.3


class ColumnMapping(BaseModel):
    """One mapping between a data column and a questionnaire variable."""

    column_name: str
    var_name: str | None = None
    question_id: str | None = None
    confidence: float = 0.0
    confidence_level: MatchConfidence = MatchConfidence.NONE
    match_reason: str = ""
    manually_edited: bool = False


class MappingVersion(BaseModel):
    """A versioned set of column-to-variable mappings."""

    mapping_id: str = Field(default_factory=lambda: f"map-{uuid.uuid4().hex[:8]}")
    project_id: str
    version: int = 1
    questionnaire_id: str
    questionnaire_version: int
    data_file_hash: str
    mappings: list[ColumnMapping]
    unmapped_columns: list[str] = Field(default_factory=list)
    locked: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def get_mapping(self, column_name: str) -> ColumnMapping | None:
        for m in self.mappings:
            if m.column_name == column_name:
                return m
        return None

    def mapped_count(self) -> int:
        return sum(1 for m in self.mappings if m.var_name is not None)

    def high_confidence_count(self) -> int:
        return sum(1 for m in self.mappings if m.confidence_level == MatchConfidence.HIGH)

    def low_confidence_mappings(self) -> list[ColumnMapping]:
        return [m for m in self.mappings if m.var_name and m.confidence_level in (MatchConfidence.LOW, MatchConfidence.NONE)]

    def for_ui(self) -> list[dict[str, Any]]:
        return [
            {
                "column_name": m.column_name,
                "var_name": m.var_name,
                "question_id": m.question_id,
                "confidence": round(m.confidence, 2),
                "confidence_level": m.confidence_level.value,
                "match_reason": m.match_reason,
                "manually_edited": m.manually_edited,
            }
            for m in self.mappings
        ]


def _confidence_level(score: float) -> MatchConfidence:
    if score >= 0.8:
        return MatchConfidence.HIGH
    if score >= 0.5:
        return MatchConfidence.MEDIUM
    if score >= 0.3:
        return MatchConfidence.LOW
    return MatchConfidence.NONE


# ---------------------------------------------------------------------------
# Matching strategies
# ---------------------------------------------------------------------------

def _exact_match(col_name: str, var_name: str) -> float:
    """Exact string match (case-insensitive)."""
    if col_name.lower() == var_name.lower():
        return 1.0
    return 0.0


def _prefix_match(col_name: str, var_name: str) -> float:
    """Check if column starts with the var prefix."""
    cn = col_name.lower().replace("_", "").replace("-", "")
    vn = var_name.lower().replace("_", "").replace("-", "")
    if cn.startswith(vn) or vn.startswith(cn):
        return 0.85
    return 0.0


def _fuzzy_match(col_name: str, var_name: str) -> float:
    """SequenceMatcher ratio."""
    return SequenceMatcher(None, col_name.lower(), var_name.lower()).ratio()


def _compute_best_match(col_name: str, variables: list[tuple[str, str]]) -> tuple[str, str, float, str]:
    """Find the best matching variable for a column.

    Args:
        col_name: Data column name.
        variables: List of (var_name, question_id) pairs.

    Returns:
        (var_name, question_id, confidence, reason)
    """
    best_var = ""
    best_qid = ""
    best_score = 0.0
    best_reason = ""

    for var_name, question_id in variables:
        # Strategy 1: Exact match
        score = _exact_match(col_name, var_name)
        if score > best_score:
            best_var, best_qid, best_score, best_reason = var_name, question_id, score, "exact_match"

        # Strategy 2: Prefix match
        score = _prefix_match(col_name, var_name)
        if score > best_score:
            best_var, best_qid, best_score, best_reason = var_name, question_id, score, "prefix_match"

        # Strategy 3: Fuzzy match
        score = _fuzzy_match(col_name, var_name)
        if score > best_score:
            best_var, best_qid, best_score, best_reason = var_name, question_id, score, "fuzzy_match"

    return best_var, best_qid, best_score, best_reason


# ---------------------------------------------------------------------------
# Auto-mapping
# ---------------------------------------------------------------------------

def auto_map(profile: DataProfile, qre: Questionnaire) -> MappingVersion:
    """Produce an auto-mapping from a data profile and questionnaire.

    Uses multi-strategy matching (exact, prefix, fuzzy) to map
    data columns to questionnaire variables.
    """
    # Build variable list from questionnaire
    variables: list[tuple[str, str]] = []
    for section in qre.sections:
        for q in section.questions:
            variables.append((q.var_name, q.question_id))

    mappings: list[ColumnMapping] = []
    used_vars: set[str] = set()
    unmapped: list[str] = []

    for col in profile.columns:
        var_name, qid, score, reason = _compute_best_match(col.name, variables)

        if score >= 0.3 and var_name not in used_vars:
            mappings.append(ColumnMapping(
                column_name=col.name,
                var_name=var_name,
                question_id=qid,
                confidence=score,
                confidence_level=_confidence_level(score),
                match_reason=reason,
            ))
            used_vars.add(var_name)
        else:
            mappings.append(ColumnMapping(
                column_name=col.name,
                confidence=0.0,
                confidence_level=MatchConfidence.NONE,
                match_reason="no_match" if score < 0.3 else "already_mapped",
            ))
            unmapped.append(col.name)

    return MappingVersion(
        project_id=qre.project_id,
        questionnaire_id=qre.questionnaire_id,
        questionnaire_version=qre.version,
        data_file_hash=profile.file_hash,
        mappings=mappings,
        unmapped_columns=unmapped,
    )


# ---------------------------------------------------------------------------
# Edit operations
# ---------------------------------------------------------------------------

def edit_mapping(
    mapping_version: MappingVersion,
    column_name: str,
    var_name: str | None,
    question_id: str | None = None,
) -> MappingVersion:
    """Edit a single column mapping. Mutates in place and returns the same version."""
    if mapping_version.locked:
        raise ValueError("Cannot edit a locked mapping. Create a new version.")

    target = mapping_version.get_mapping(column_name)
    if not target:
        raise ValueError(f"Column {column_name!r} not found in mapping.")

    # Duplicate variable guard: reject if another column already uses this var_name
    if var_name is not None:
        for m in mapping_version.mappings:
            if m.column_name != column_name and m.var_name == var_name:
                raise ValueError(
                    f"Variable '{var_name}' is already mapped to column '{m.column_name}'. "
                    "Unmap it first or choose a different variable."
                )

    target.var_name = var_name
    target.question_id = question_id
    target.confidence = 1.0 if var_name else 0.0
    target.confidence_level = MatchConfidence.HIGH if var_name else MatchConfidence.NONE
    target.match_reason = "manual_edit"
    target.manually_edited = True
    mapping_version.updated_at = datetime.now(tz=timezone.utc)

    # Update unmapped list
    mapping_version.unmapped_columns = [
        m.column_name for m in mapping_version.mappings if m.var_name is None
    ]

    return mapping_version


# ---------------------------------------------------------------------------
# Version store
# ---------------------------------------------------------------------------

class MappingStore:
    """In-memory mapping version store.

    TODO: Back with database for persistence.
    """

    def __init__(self) -> None:
        self._versions: dict[str, list[MappingVersion]] = {}  # keyed by project_id

    def save(self, mapping: MappingVersion) -> MappingVersion:
        """Save a mapping version with auto-incremented version number."""
        pid = mapping.project_id
        if pid not in self._versions:
            self._versions[pid] = []
        existing = self._versions[pid]
        max_version = max((v.version for v in existing), default=0)
        mapping.version = max_version + 1
        self._versions[pid].append(mapping)
        return mapping

    def get_latest(self, project_id: str) -> MappingVersion | None:
        versions = self._versions.get(project_id, [])
        return versions[-1] if versions else None

    def get_version(self, project_id: str, version: int) -> MappingVersion | None:
        for v in self._versions.get(project_id, []):
            if v.version == version:
                return v
        return None

    def list_versions(self, project_id: str) -> list[dict[str, Any]]:
        return [
            {
                "mapping_id": v.mapping_id,
                "version": v.version,
                "questionnaire_version": v.questionnaire_version,
                "data_file_hash": v.data_file_hash,
                "mapped_count": v.mapped_count(),
                "unmapped_count": len(v.unmapped_columns),
                "locked": v.locked,
                "created_at": v.created_at.isoformat(),
            }
            for v in self._versions.get(project_id, [])
        ]

    @property
    def count(self) -> int:
        return sum(len(v) for v in self._versions.values())
