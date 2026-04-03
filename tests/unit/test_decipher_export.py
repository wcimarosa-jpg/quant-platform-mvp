"""Contract tests for Decipher-ready structured export (P04-04).

AC-1: Structured output includes questions, options, logic, IDs.
AC-2: Internal schema checks pass.
AC-3: Export artifact stored with questionnaire/version linkage.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from packages.shared.assistant_context import (
    AssistantContext,
    BriefContext,
    Methodology,
    WorkflowStage,
)
from packages.shared.draft_config import DraftStore
from packages.shared.questionnaire_schema import (
    Question,
    QuestionType,
    Questionnaire,
    ResponseOption,
    Section,
)
from packages.exporters.decipher_export import (
    DecipherValidationError,
    ExportArtifact,
    export_questionnaire_decipher,
    generate_decipher_structure,
    _validate_decipher_output,
)
from packages.survey_generation.engine import generate_questionnaire

NOW = datetime.now(tz=timezone.utc)


def _generate() -> Questionnaire:
    store = DraftStore()
    draft = store.create("proj-001", Methodology.SEGMENTATION)
    ctx = AssistantContext(
        project_id="proj-001",
        stage=WorkflowStage.QUESTIONNAIRE,
        methodology=Methodology.SEGMENTATION,
        brief=BriefContext(
            brief_id="brief-001", objectives="Test", audience="Adults",
            category="snack bars", geography="US", uploaded_at=NOW,
        ),
        selected_sections=["screener", "attitudes", "demographics"],
    )
    return generate_questionnaire(draft, ctx)


def _parse_artifact(artifact: ExportArtifact) -> dict:
    return json.loads(artifact.content.decode("utf-8"))


# ---------------------------------------------------------------------------
# AC-1: Structured output includes questions, options, logic, IDs
# ---------------------------------------------------------------------------

class TestStructuredOutput:
    def test_output_has_metadata(self):
        qre = _generate()
        structure = generate_decipher_structure(qre)
        assert "metadata" in structure
        meta = structure["metadata"]
        assert meta["questionnaire_id"] == qre.questionnaire_id
        assert meta["version"] == qre.version
        assert meta["methodology"] == "segmentation"
        assert meta["project_id"] == "proj-001"

    def test_output_has_sections(self):
        qre = _generate()
        structure = generate_decipher_structure(qre)
        assert "sections" in structure
        assert len(structure["sections"]) >= 3

    def test_sections_have_questions(self):
        qre = _generate()
        structure = generate_decipher_structure(qre)
        for section in structure["sections"]:
            assert "questions" in section
            assert "section_type" in section
            assert "label" in section

    def test_questions_have_ids_and_var_names(self):
        qre = _generate()
        structure = generate_decipher_structure(qre)
        for section in structure["sections"]:
            for q in section["questions"]:
                assert "question_id" in q
                assert "var_name" in q
                assert q["question_id"]
                assert q["var_name"]

    def test_questions_have_decipher_types(self):
        qre = _generate()
        structure = generate_decipher_structure(qre)
        valid_types = {"radio", "checkbox", "number", "textarea", "maxdiff", "ranking"}
        for section in structure["sections"]:
            for q in section["questions"]:
                assert q["question_type"] in valid_types

    def test_response_options_included(self):
        qre = _generate()
        structure = generate_decipher_structure(qre)
        screener = next(s for s in structure["sections"] if s["section_type"] == "screener")
        radio_q = next(q for q in screener["questions"] if q["question_type"] == "radio")
        assert "options" in radio_q
        assert len(radio_q["options"]) >= 2
        for opt in radio_q["options"]:
            assert "code" in opt
            assert "label" in opt

    def test_termination_flags_included(self):
        qre = _generate()
        structure = generate_decipher_structure(qre)
        screener = next(s for s in structure["sections"] if s["section_type"] == "screener")
        all_opts = [opt for q in screener["questions"] for opt in q.get("options", [])]
        assert any(opt["terminates"] for opt in all_opts)

    def test_scale_labels_included(self):
        qre = _generate()
        structure = generate_decipher_structure(qre)
        attitudes = next(s for s in structure["sections"] if s["section_type"] == "attitudes")
        likert_q = attitudes["questions"][0]
        assert "scale_points" in likert_q
        assert "scale_labels" in likert_q

    def test_logic_notes_included_when_present(self):
        qre = Questionnaire(
            project_id="proj-001", methodology="segmentation",
            sections=[Section(section_id="s1", section_type="test", label="T", order=0,
                              questions=[
                                  Question(question_id="Q1", question_text="Q?",
                                           question_type=QuestionType.OPEN_ENDED, var_name="Q1",
                                           logic="Show if SCR_01 == 1"),
                              ])],
        )
        structure = generate_decipher_structure(qre)
        q = structure["sections"][0]["questions"][0]
        assert q["logic"] == "Show if SCR_01 == 1"

    def test_format_field_present(self):
        qre = _generate()
        structure = generate_decipher_structure(qre)
        assert structure["format"] == "decipher_v1"


# ---------------------------------------------------------------------------
# AC-2: Internal schema checks pass
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    def test_valid_output_passes(self):
        qre = _generate()
        structure = generate_decipher_structure(qre)
        errors = _validate_decipher_output(structure)
        assert errors == []

    def test_missing_metadata_fails(self):
        errors = _validate_decipher_output({"sections": []})
        assert any("metadata" in e for e in errors)

    def test_missing_sections_fails(self):
        errors = _validate_decipher_output({"metadata": {
            "questionnaire_id": "x", "version": 1, "methodology": "x", "project_id": "x"
        }})
        assert any("sections" in e for e in errors)

    def test_missing_question_fields_fails(self):
        errors = _validate_decipher_output({
            "metadata": {"questionnaire_id": "x", "version": 1, "methodology": "x", "project_id": "x"},
            "sections": [{"section_type": "t", "questions": [{}]}],
        })
        assert len(errors) >= 1

    def test_duplicate_question_id_fails(self):
        errors = _validate_decipher_output({
            "metadata": {"questionnaire_id": "x", "version": 1, "methodology": "x", "project_id": "x"},
            "sections": [{
                "section_type": "t",
                "questions": [
                    {"question_id": "Q1", "var_name": "Q1", "question_type": "textarea", "question_text": "A?"},
                    {"question_id": "Q1", "var_name": "Q2", "question_type": "textarea", "question_text": "B?"},
                ],
            }],
        })
        assert any("Duplicate" in e for e in errors)

    def test_radio_without_options_fails(self):
        errors = _validate_decipher_output({
            "metadata": {"questionnaire_id": "x", "version": 1, "methodology": "x", "project_id": "x"},
            "sections": [{
                "section_type": "t",
                "questions": [
                    {"question_id": "Q1", "var_name": "Q1", "question_type": "radio", "question_text": "Q?"},
                ],
            }],
        })
        assert any("options" in e.lower() for e in errors)

    def test_export_raises_on_invalid(self):
        """Export function should raise DecipherValidationError for bad data."""
        qre = Questionnaire(
            project_id="proj-001", methodology="segmentation",
            sections=[Section(section_id="s1", section_type="t", label="T", order=0,
                              questions=[
                                  Question(question_id="Q1", question_text="Q?",
                                           question_type=QuestionType.SINGLE_SELECT, var_name="Q1",
                                           response_options=[ResponseOption(code=1, label="A")]),
                                  Question(question_id="Q1", question_text="Dup",
                                           question_type=QuestionType.OPEN_ENDED, var_name="Q1b"),
                              ])],
        )
        with pytest.raises(DecipherValidationError) as exc_info:
            export_questionnaire_decipher(qre)
        assert len(exc_info.value.errors) >= 1


# ---------------------------------------------------------------------------
# AC-3: Export artifact stored with questionnaire/version linkage
# ---------------------------------------------------------------------------

class TestArtifactLinkage:
    def test_export_returns_artifact(self):
        qre = _generate()
        artifact = export_questionnaire_decipher(qre)
        assert isinstance(artifact, ExportArtifact)

    def test_artifact_links_to_questionnaire(self):
        qre = _generate()
        artifact = export_questionnaire_decipher(qre)
        assert artifact.questionnaire_id == qre.questionnaire_id
        assert artifact.version == qre.version

    def test_artifact_format_is_decipher(self):
        qre = _generate()
        artifact = export_questionnaire_decipher(qre)
        assert artifact.format == "decipher_json"

    def test_filename_includes_project_and_version(self):
        qre = _generate()
        artifact = export_questionnaire_decipher(qre)
        assert "proj-001" in artifact.filename
        assert "v1" in artifact.filename
        assert artifact.filename.endswith(".json")

    def test_content_is_valid_json(self):
        qre = _generate()
        artifact = export_questionnaire_decipher(qre)
        parsed = _parse_artifact(artifact)
        assert parsed["format"] == "decipher_v1"
        assert len(parsed["sections"]) >= 3

    def test_provenance_metadata(self):
        qre = _generate()
        artifact = export_questionnaire_decipher(qre)
        prov = artifact.provenance()
        assert prov["questionnaire_id"] == qre.questionnaire_id
        assert prov["version"] == qre.version
        assert prov["format"] == "decipher_json"
        assert prov["size_bytes"] > 0

    def test_save_to_disk(self, tmp_path: Path):
        qre = _generate()
        artifact = export_questionnaire_decipher(qre)
        path = artifact.save_to(tmp_path / "Outputs")
        assert path.exists()
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["metadata"]["questionnaire_id"] == qre.questionnaire_id
