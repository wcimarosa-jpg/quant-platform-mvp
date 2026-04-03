"""Decipher-ready structured export.

Generates a JSON structure compatible with Decipher survey platform
import workflows. Includes questions, options, logic, IDs, and
variable naming in Decipher conventions.
"""

from __future__ import annotations

import json
from typing import Any

from packages.shared.questionnaire_schema import (
    Question,
    QuestionType,
    Questionnaire,
    ResponseOption,
    Section,
)
from packages.exporters.docx_export import ExportArtifact


# ---------------------------------------------------------------------------
# Decipher question type mapping
# ---------------------------------------------------------------------------

_DECIPHER_QTYPES: dict[QuestionType, str] = {
    QuestionType.SINGLE_SELECT: "radio",
    QuestionType.MULTI_SELECT: "checkbox",
    QuestionType.LIKERT_SCALE: "radio",       # Decipher uses radio grids for Likert
    QuestionType.NUMERIC: "number",
    QuestionType.OPEN_ENDED: "textarea",
    QuestionType.MAXDIFF_TASK: "maxdiff",
    QuestionType.RANKING: "ranking",
}


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class DecipherValidationError(Exception):
    """Raised when the structured output fails internal schema checks."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"{len(errors)} schema error(s): {'; '.join(errors[:3])}")


def _validate_decipher_output(output: dict[str, Any]) -> list[str]:
    """Run internal schema checks on the Decipher export structure."""
    errors: list[str] = []

    if "metadata" not in output:
        errors.append("Missing 'metadata' key.")
    else:
        meta = output["metadata"]
        for field in ("questionnaire_id", "version", "methodology", "project_id"):
            if field not in meta:
                errors.append(f"metadata missing '{field}'.")

    if "sections" not in output:
        errors.append("Missing 'sections' key.")
        return errors

    seen_ids: set[str] = set()
    for i, section in enumerate(output["sections"]):
        if "section_type" not in section:
            errors.append(f"Section {i}: missing 'section_type'.")
        if "questions" not in section:
            errors.append(f"Section {i}: missing 'questions'.")
            continue

        for j, q in enumerate(section["questions"]):
            for field in ("question_id", "var_name", "question_type", "question_text"):
                if field not in q:
                    errors.append(f"Section {i}, Q{j}: missing '{field}'.")

            qid = q.get("question_id", "")
            if qid in seen_ids:
                errors.append(f"Duplicate question_id: '{qid}'.")
            seen_ids.add(qid)

            qtype = q.get("question_type", "")
            if qtype in ("radio", "checkbox") and not q.get("options"):
                errors.append(f"Q '{qid}': type '{qtype}' requires 'options'.")

    return errors


# ---------------------------------------------------------------------------
# Export generation
# ---------------------------------------------------------------------------

def _convert_question(q: Question) -> dict[str, Any]:
    """Convert a Question to Decipher-compatible structure."""
    out: dict[str, Any] = {
        "question_id": q.question_id,
        "var_name": q.var_name,
        "question_type": _DECIPHER_QTYPES.get(q.question_type, q.question_type.value),
        "question_text": q.question_text,
        "required": q.required,
    }

    if q.response_options:
        out["options"] = [
            {
                "code": opt.code,
                "label": opt.label,
                "terminates": opt.terminates,
            }
            for opt in q.response_options
        ]
    elif q.scale_points and q.scale_labels:
        # Generate options from scale labels for Likert items (Decipher needs radio options)
        out["options"] = [
            {"code": k, "label": v, "terminates": False}
            for k, v in sorted(q.scale_labels.items())
        ]

    if q.scale_points:
        out["scale_points"] = q.scale_points
    if q.scale_labels:
        out["scale_labels"] = {str(k): v for k, v in q.scale_labels.items()}

    if q.logic:
        out["logic"] = q.logic

    return out


def _convert_section(section: Section) -> dict[str, Any]:
    """Convert a Section to Decipher-compatible structure."""
    return {
        "section_id": section.section_id,
        "section_type": section.section_type,
        "label": section.label,
        "order": section.order,
        "questions": [_convert_question(q) for q in section.questions],
        "metadata": section.metadata,
    }


def generate_decipher_structure(qre: Questionnaire) -> dict[str, Any]:
    """Generate the full Decipher-ready JSON structure."""
    return {
        "format": "decipher_v1",
        "metadata": {
            "questionnaire_id": qre.questionnaire_id,
            "version": qre.version,
            "methodology": qre.methodology,
            "project_id": qre.project_id,
            "total_questions": qre.total_questions,
            "estimated_loi_minutes": qre.estimated_loi_minutes,
            "context_hash": qre.context_hash,
        },
        "sections": [_convert_section(s) for s in qre.sections],
    }


def export_questionnaire_decipher(qre: Questionnaire) -> ExportArtifact:
    """Generate a Decipher-ready structured export.

    Returns an ExportArtifact with validated JSON content and provenance.
    Raises DecipherValidationError if internal schema checks fail.
    """
    structure = generate_decipher_structure(qre)

    # Internal schema checks (AC-2)
    errors = _validate_decipher_output(structure)
    if errors:
        raise DecipherValidationError(errors)

    content = json.dumps(structure, indent=2, ensure_ascii=False).encode("utf-8")
    filename = f"{qre.project_id}_decipher_v{qre.version}.json"

    return ExportArtifact(
        content=content,
        filename=filename,
        questionnaire_id=qre.questionnaire_id,
        version=qre.version,
        format="decipher_json",
    )
