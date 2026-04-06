"""E2E tests: full research workflow journey (P08-03).

AC-1: brief → questionnaire → mapping → tables → analysis → exports
AC-2: Known failure paths tested
AC-3: UAT checklist passes for in-scope methodologies

These tests exercise the entire pipeline end-to-end using real
computation (no stubs, no mocks).
"""

from __future__ import annotations

import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# --- Brief ---
from packages.shared.brief_parser import ingest_brief
from packages.shared.brief_analyzer import analyze_brief, apply_accepted_assumptions, resolve_assumption, AssumptionStatus
from packages.shared.preflight import run_preflight

# --- Questionnaire ---
from packages.shared.assistant_context import AssistantContext, BriefContext, Methodology, WorkflowStage
from packages.shared.draft_config import DraftStore
from packages.survey_generation.engine import generate_questionnaire
from packages.survey_generation.section_editor import regenerate_section

# --- Validation & Export ---
from packages.shared.validation_engine import validate_questionnaire
from packages.exporters.docx_export import export_questionnaire_docx
from packages.exporters.decipher_export import export_questionnaire_decipher

# --- Data & Mapping ---
from packages.shared.data_profiler import profile_data
from packages.shared.mapping_engine import auto_map

# --- Tables & QA ---
from packages.survey_analysis.table_generator import generate_tables, TableConfig, TableType, save_run
from packages.survey_analysis.table_qa import run_table_qa, save_qa_report

# --- Analysis ---
from packages.survey_analysis.run_orchestrator import RunConfig, RunVersions, RunStore, create_run, execute_run
from packages.survey_analysis.result_schemas import validate_result

# --- Insights ---
from packages.survey_analysis.insight_evidence import extract_evidence
from packages.survey_analysis.insight_narrative import generate_narrative, NarrativeDepth
from packages.survey_analysis.run_comparison import compare_runs

# Ensure analysis modules registered
import packages.survey_analysis.drivers  # noqa: F401
import packages.survey_analysis.segmentation  # noqa: F401
import packages.survey_analysis.maxdiff_turf  # noqa: F401

NOW = datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Synthetic data that mimics a real survey export
# ---------------------------------------------------------------------------

def _survey_csv(n: int = 200) -> bytes:
    rng = np.random.RandomState(42)
    df = pd.DataFrame({
        "SCR_01": rng.choice([1, 2, 3, 4], size=n, p=[0.4, 0.3, 0.2, 0.1]),
        "ATT_01": rng.choice([1, 2, 3, 4, 5], size=n),
        "ATT_02": rng.choice([1, 2, 3, 4, 5], size=n),
        "ATT_03": rng.choice([1, 2, 3, 4, 5], size=n),
        "ATT_04": rng.choice([1, 2, 3, 4, 5], size=n),
        "ATT_05": rng.choice([1, 2, 3, 4, 5], size=n),
        "ATT_06": rng.choice([1, 2, 3, 4, 5], size=n),
        "ATT_07": rng.choice([1, 2, 3, 4, 5], size=n),
        "ATT_08": rng.choice([1, 2, 3, 4, 5], size=n),
        "ATT_09": rng.choice([1, 2, 3, 4, 5], size=n),
        "ATT_10": rng.choice([1, 2, 3, 4, 5], size=n),
        "SAT_01": rng.choice([1, 2, 3, 4, 5], size=n, p=[0.05, 0.1, 0.2, 0.35, 0.3]),
        "NPS": rng.choice(range(11), size=n),
        "DEM_01": rng.choice([1, 2], size=n),
        "DEM_02": rng.choice([1, 2, 3, 4], size=n),
        "GENDER": rng.choice([1, 2], size=n),
    })
    return df.to_csv(index=False).encode("utf-8")


SAMPLE_BRIEF = """# Research Brief: Premium Snack Bar Brand Health

## Research Objectives:
Understand how consumers perceive KIND Bars compared to competitors.
Identify growth opportunities among lapsed users.

## Target Audience:
US adults 18-54 who purchase snack bars monthly.

## Product Category:
Premium snack bars

## Geographic Scope:
United States

## Constraints:
LOI max 15 minutes, n=1000
"""


# ---------------------------------------------------------------------------
# AC-1: Full journey — brief → questionnaire → mapping → tables → analysis → exports
# ---------------------------------------------------------------------------

class TestFullJourney:
    """End-to-end test of the complete research workflow."""

    def test_segmentation_journey(self, tmp_path: Path):
        """Full segmentation pipeline: brief through insight narrative."""

        # === STEP 1: Brief ingestion ===
        brief_fields = ingest_brief(SAMPLE_BRIEF.encode("utf-8"), "brief.md")
        assert brief_fields.is_complete()
        assert "KIND Bars" in brief_fields.objectives

        # === STEP 2: Preflight gate ===
        preflight = run_preflight(brief_fields, Methodology.SEGMENTATION)
        assert preflight.can_generate

        # === STEP 3: Methodology + section selection ===
        draft_store = DraftStore()
        draft = draft_store.create("proj-e2e", Methodology.SEGMENTATION)
        assert len(draft.selected_sections) >= 3

        # === STEP 4: Questionnaire generation ===
        ctx = AssistantContext(
            project_id="proj-e2e",
            stage=WorkflowStage.QUESTIONNAIRE,
            methodology=Methodology.SEGMENTATION,
            brief=brief_fields.to_brief_context("brief-e2e"),
            selected_sections=draft.selected_sections,
        )
        qre = generate_questionnaire(draft, ctx)
        assert qre.total_questions > 0
        assert len(qre.sections) >= 3

        # === STEP 5: Validation ===
        report = validate_questionnaire(qre)
        assert report.can_publish

        # === STEP 6: Export DOCX + Decipher ===
        docx_artifact = export_questionnaire_docx(qre)
        assert docx_artifact.size_bytes > 0
        docx_artifact.save_to(tmp_path / "exports")

        decipher_artifact = export_questionnaire_decipher(qre)
        assert decipher_artifact.size_bytes > 0

        # === STEP 7: Data upload + profiling ===
        csv_bytes = _survey_csv()
        file_meta, data_profile = profile_data(csv_bytes, "survey_data.csv")
        assert data_profile.row_count == 200
        assert data_profile.column_count >= 10

        # === STEP 8: Auto-mapping ===
        mapping = auto_map(data_profile, qre)
        assert mapping.mapped_count() > 0

        # === STEP 9: Table generation ===
        variables = [
            {"var_name": "SCR_01", "question_id": "SCR_01"},
            {"var_name": "SAT_01", "question_id": "SAT_01"},
        ]
        df = pd.read_csv(io.BytesIO(csv_bytes))
        config = TableConfig(
            table_types=[TableType.FREQUENCY, TableType.MEAN],
            banner_variables=["GENDER"],
        )
        table_result = generate_tables(
            project_id="proj-e2e", mapping_id=mapping.mapping_id,
            mapping_version=mapping.version, questionnaire_version=qre.version,
            variables=variables, df=df, config=config,
        )
        assert table_result.total_tables >= 4
        run_dir = save_run(table_result, tmp_path / "Runs")

        # === STEP 10: Table QA ===
        qa_report = run_table_qa(table_result)
        assert qa_report.passed
        save_qa_report(qa_report, run_dir)

        # === STEP 11: Analysis (drivers) ===
        iv_cols = [f"ATT_{i:02d}" for i in range(1, 11)]
        dv_cols = ["SAT_01", "NPS"]
        run = create_run("proj-e2e", RunConfig(analysis_type="drivers"), RunVersions(
            questionnaire_id=qre.questionnaire_id, questionnaire_version=qre.version,
            mapping_id=mapping.mapping_id, mapping_version=mapping.version,
            data_file_hash=file_meta.file_hash,
        ))
        execute_run(run, df=df, iv_cols=iv_cols, dv_cols=dv_cols)
        assert run.status.value == "completed"
        validated = validate_result("drivers", run.result_summary)
        assert validated is not None

        # === STEP 12: Insight narrative ===
        bundle = extract_evidence(run.run_id, "drivers", run.result_summary)
        assert len(bundle.evidence) > 0
        narrative = generate_narrative(bundle, NarrativeDepth.PLAIN)
        assert narrative.unsupported_claims == 0
        assert len(narrative.statements) > 0

        # === STEP 13: Verify all artifacts exist ===
        assert (tmp_path / "exports" / docx_artifact.filename).exists()
        assert (run_dir / "manifest.json").exists()
        assert (run_dir / "qa_report.json").exists()


# ---------------------------------------------------------------------------
# AC-2: Known failure paths
# ---------------------------------------------------------------------------

class TestFailurePaths:
    def test_incomplete_brief_blocks_generation(self):
        brief = ingest_brief(b"# Brief\n\nObjectives: Test concepts.", "short.md")
        preflight = run_preflight(brief, Methodology.SEGMENTATION)
        assert preflight.can_generate is False
        assert preflight.blocking_count >= 1

    def test_empty_data_rejects(self):
        with pytest.raises(Exception):
            profile_data(b"", "empty.csv")

    def test_missing_analysis_column_fails(self):
        df = pd.DataFrame({"X": [1, 2, 3]})
        run = create_run("proj-fail", RunConfig(analysis_type="drivers"), RunVersions(
            questionnaire_id="q", questionnaire_version=1,
            mapping_id="m", mapping_version=1, data_file_hash="h",
        ))
        execute_run(run, df=df, iv_cols=["NONEXISTENT"], dv_cols=["X"])
        assert run.status.value == "failed"
        assert "NONEXISTENT" in run.error_message

    def test_validation_blocks_bad_questionnaire(self):
        from packages.shared.questionnaire_schema import Questionnaire, Section, Question, QuestionType, ResponseOption
        qre = Questionnaire(
            project_id="proj-fail", methodology="segmentation",
            sections=[Section(
                section_id="s1", section_type="screener", label="S", order=0,
                questions=[Question(
                    question_id="Q1", question_text="Q?",
                    question_type=QuestionType.SINGLE_SELECT, var_name="Q1",
                    response_options=[ResponseOption(code=1, label="Only one")],
                )],
            )],
        )
        report = validate_questionnaire(qre)
        assert report.can_publish is False

    def test_compare_non_completed_run_fails(self):
        r1 = create_run("p", RunConfig(analysis_type="drivers"), RunVersions(
            questionnaire_id="q", questionnaire_version=1,
            mapping_id="m", mapping_version=1, data_file_hash="h",
        ))
        r2 = create_run("p", RunConfig(analysis_type="drivers"), RunVersions(
            questionnaire_id="q", questionnaire_version=1,
            mapping_id="m", mapping_version=1, data_file_hash="h",
        ))
        with pytest.raises(ValueError, match="not completed"):
            compare_runs(r1, r2)

    def test_unsupported_file_format_rejects(self):
        with pytest.raises(Exception):
            profile_data(b"data", "file.xlsx.bak")


# ---------------------------------------------------------------------------
# AC-3: UAT checklist for in-scope methodologies
# ---------------------------------------------------------------------------

class TestUATChecklist:
    """Verify each methodology can complete the core journey."""

    @pytest.mark.parametrize("methodology", [
        Methodology.SEGMENTATION,
        Methodology.ATTITUDE_USAGE,
        Methodology.DRIVERS,
        Methodology.CONCEPT_MONADIC,
        Methodology.CREATIVE_MONADIC,
        Methodology.BRAND_EQUITY_TRACKER,
        Methodology.MAXDIFF,
        Methodology.TURF,
    ])
    def test_methodology_can_generate_questionnaire(self, methodology: Methodology):
        """Each methodology produces a valid questionnaire."""
        brief = BriefContext(
            brief_id="brief-uat", objectives="UAT test", audience="Adults",
            category="Test", geography="US", uploaded_at=NOW,
        )
        store = DraftStore()
        draft = store.create("proj-uat", methodology)
        ctx = AssistantContext(
            project_id="proj-uat", stage=WorkflowStage.QUESTIONNAIRE,
            methodology=methodology, brief=brief,
            selected_sections=draft.selected_sections,
        )
        qre = generate_questionnaire(draft, ctx)
        assert qre.total_questions > 0
        assert len(qre.sections) >= 3

    @pytest.mark.parametrize("methodology", [
        Methodology.SEGMENTATION,
        Methodology.ATTITUDE_USAGE,
        Methodology.DRIVERS,
        Methodology.CONCEPT_MONADIC,
        Methodology.CREATIVE_MONADIC,
        Methodology.BRAND_EQUITY_TRACKER,
        Methodology.MAXDIFF,
        Methodology.TURF,
    ])
    def test_methodology_questionnaire_validates(self, methodology: Methodology):
        """Each methodology's questionnaire passes validation."""
        brief = BriefContext(
            brief_id="brief-uat", objectives="UAT", audience="Adults",
            category="Test", geography="US", uploaded_at=NOW,
        )
        store = DraftStore()
        draft = store.create("proj-uat", methodology)
        ctx = AssistantContext(
            project_id="proj-uat", stage=WorkflowStage.QUESTIONNAIRE,
            methodology=methodology, brief=brief,
            selected_sections=draft.selected_sections,
        )
        qre = generate_questionnaire(draft, ctx)
        report = validate_questionnaire(qre)
        assert report.can_publish, f"{methodology.value}: {[i.message for i in report.errors()]}"

    @pytest.mark.parametrize("methodology", [
        Methodology.SEGMENTATION,
        Methodology.ATTITUDE_USAGE,
        Methodology.DRIVERS,
        Methodology.CONCEPT_MONADIC,
        Methodology.CREATIVE_MONADIC,
        Methodology.BRAND_EQUITY_TRACKER,
        Methodology.MAXDIFF,
        Methodology.TURF,
    ])
    def test_methodology_exports_docx(self, methodology: Methodology):
        """Each methodology can export to DOCX."""
        brief = BriefContext(
            brief_id="brief-uat", objectives="UAT", audience="Adults",
            category="Test", geography="US", uploaded_at=NOW,
        )
        store = DraftStore()
        draft = store.create("proj-uat", methodology)
        ctx = AssistantContext(
            project_id="proj-uat", stage=WorkflowStage.QUESTIONNAIRE,
            methodology=methodology, brief=brief,
            selected_sections=draft.selected_sections,
        )
        qre = generate_questionnaire(draft, ctx)
        artifact = export_questionnaire_docx(qre)
        assert artifact.size_bytes > 0

    def test_drivers_analysis_e2e(self):
        """Drivers: data → analysis → insight → narrative."""
        from data.fixtures.small.p07_synthetic import make_survey_df, iv_columns, dv_columns
        df = make_survey_df()
        run = create_run("proj-uat", RunConfig(analysis_type="drivers"), RunVersions(
            questionnaire_id="q", questionnaire_version=1,
            mapping_id="m", mapping_version=1, data_file_hash="h",
        ))
        execute_run(run, df=df, iv_cols=iv_columns()[:10], dv_cols=dv_columns())
        assert run.status.value == "completed"
        bundle = extract_evidence(run.run_id, "drivers", run.result_summary)
        narrative = generate_narrative(bundle, NarrativeDepth.ANALYST)
        assert narrative.unsupported_claims == 0

    def test_segmentation_analysis_e2e(self):
        """Segmentation: data → VarClus → KMeans → profiles → insight."""
        from data.fixtures.small.p07_synthetic import make_survey_df, iv_columns
        df = make_survey_df()
        run = create_run("proj-uat", RunConfig(analysis_type="segmentation"), RunVersions(
            questionnaire_id="q", questionnaire_version=1,
            mapping_id="m", mapping_version=1, data_file_hash="h",
        ))
        execute_run(run, df=df, clustering_vars=iv_columns(), profile_vars=["GENDER", "AGE_GROUP"])
        assert run.status.value == "completed"
        bundle = extract_evidence(run.run_id, "segmentation", run.result_summary)
        narrative = generate_narrative(bundle)
        assert narrative.unsupported_claims == 0

    def test_maxdiff_turf_analysis_e2e(self):
        """MaxDiff+TURF: data → scoring → reach → insight."""
        from data.fixtures.small.p07_synthetic import make_survey_df, maxdiff_items, turf_acceptance_columns
        df = make_survey_df()
        run = create_run("proj-uat", RunConfig(analysis_type="maxdiff_turf"), RunVersions(
            questionnaire_id="q", questionnaire_version=1,
            mapping_id="m", mapping_version=1, data_file_hash="h",
        ))
        execute_run(run, df=df, maxdiff_columns=maxdiff_items(), acceptance_columns=turf_acceptance_columns())
        assert run.status.value == "completed"
        bundle = extract_evidence(run.run_id, "maxdiff_turf", run.result_summary)
        narrative = generate_narrative(bundle, NarrativeDepth.PLAIN)
        assert narrative.unsupported_claims == 0

    def test_brief_assumption_workflow(self):
        """Brief → analyze → accept assumptions → becomes complete."""
        brief = ingest_brief(b"# Brief\n\nObjectives: Test new concepts.", "short.md")
        assert not brief.is_complete()
        analysis = analyze_brief("brief-uat", brief)
        assert len(analysis.gaps) >= 1
        assert len(analysis.assumptions) >= 1
        for a in analysis.assumptions:
            resolve_assumption(analysis, a.assumption_id, AssumptionStatus.ACCEPTED)
        apply_accepted_assumptions(brief, analysis)
        assert brief.is_complete()

    def test_section_regeneration_workflow(self):
        """Generate → regenerate one section → others untouched."""
        brief = BriefContext(
            brief_id="brief-regen", objectives="Test", audience="Adults",
            category="Snacks", geography="US", uploaded_at=NOW,
        )
        store = DraftStore()
        draft = store.create("proj-regen", Methodology.SEGMENTATION)
        ctx = AssistantContext(
            project_id="proj-regen", stage=WorkflowStage.QUESTIONNAIRE,
            methodology=Methodology.SEGMENTATION, brief=brief,
            selected_sections=draft.selected_sections,
        )
        qre = generate_questionnaire(draft, ctx)
        original_sections = {s.section_type: [q.question_id for q in s.questions] for s in qre.sections}
        result = regenerate_section(qre, "screener", "Simplify the screener", ctx)
        for s in qre.sections:
            if s.section_type != "screener":
                assert [q.question_id for q in s.questions] == original_sections[s.section_type]
        assert result.new_version == 2

    def test_run_comparison_happy_path(self):
        """Compare two completed drivers runs and get diffs + explanations."""
        from data.fixtures.small.p07_synthetic import make_survey_df, iv_columns, dv_columns
        r1 = create_run("proj-cmp", RunConfig(analysis_type="drivers"), RunVersions(
            questionnaire_id="q", questionnaire_version=1,
            mapping_id="m", mapping_version=1, data_file_hash="sha256:v1",
        ))
        execute_run(r1, df=make_survey_df(seed=42), iv_cols=iv_columns()[:10], dv_cols=dv_columns())
        assert r1.status.value == "completed"

        r2 = create_run("proj-cmp", RunConfig(analysis_type="drivers"), RunVersions(
            questionnaire_id="q", questionnaire_version=1,
            mapping_id="m", mapping_version=2, data_file_hash="sha256:v2",
        ))
        execute_run(r2, df=make_survey_df(seed=99), iv_cols=iv_columns()[:10], dv_cols=dv_columns())
        assert r2.status.value == "completed"

        comp = compare_runs(r1, r2)
        assert comp.base_run_id == r1.run_id
        assert comp.compare_run_id == r2.run_id
        changed_fields = [d.field for d in comp.version_diffs if d.changed]
        assert "mapping_version" in changed_fields
        assert "data_file_hash" in changed_fields
        assert len(comp.metric_deltas) > 0
        assert len(comp.explanations) > 0
        assert comp.summary
