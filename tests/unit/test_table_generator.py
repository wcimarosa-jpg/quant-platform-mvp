"""Contract tests for core table generation pipeline (P06-01).

AC-1: Core tables generate from saved mapping without manual edits.
AC-2: Significance toggle is configurable.
AC-3: Output artifacts stored under run folder.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.survey_analysis.table_generator import (
    GeneratedTable,
    SignificanceConfig,
    TableCell,
    TableConfig,
    TableRow,
    TableRunResult,
    TableType,
    generate_tables,
    save_run,
)


def _variables() -> list[dict[str, str]]:
    return [
        {"var_name": "SCR_01", "question_id": "Q1", "question_text": "Category usage?"},
        {"var_name": "ATT_01", "question_id": "Q2", "question_text": "I research products"},
        {"var_name": "SAT_01", "question_id": "Q3", "question_text": "Overall satisfaction?"},
    ]


# ---------------------------------------------------------------------------
# AC-1: Core tables generate from saved mapping without manual edits
# ---------------------------------------------------------------------------

class TestTableGeneration:
    def test_generates_tables(self):
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=_variables(),
        )
        assert isinstance(result, TableRunResult)
        assert result.total_tables > 0

    def test_generates_all_configured_types(self):
        config = TableConfig(table_types=[TableType.FREQUENCY, TableType.MEAN, TableType.TOP2BOX])
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=_variables(), config=config,
        )
        types_generated = {t.table_type for t in result.tables}
        assert TableType.FREQUENCY in types_generated
        assert TableType.MEAN in types_generated
        assert TableType.TOP2BOX in types_generated

    def test_one_table_per_variable_per_type(self):
        config = TableConfig(table_types=[TableType.FREQUENCY])
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=_variables(), config=config,
        )
        assert result.total_tables == 3  # 3 variables x 1 type

    def test_frequency_table_has_rows(self):
        config = TableConfig(table_types=[TableType.FREQUENCY])
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=_variables(), config=config,
        )
        table = result.tables[0]
        assert len(table.rows) >= 2
        assert table.table_type == TableType.FREQUENCY

    def test_mean_table_has_mean_and_stddev(self):
        config = TableConfig(table_types=[TableType.MEAN])
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=_variables(), config=config,
        )
        table = result.tables[0]
        labels = [r.label for r in table.rows]
        assert "Mean" in labels
        assert "Std Dev" in labels

    def test_t2b_table_has_top_and_bottom(self):
        config = TableConfig(table_types=[TableType.TOP2BOX])
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=_variables(), config=config,
        )
        table = result.tables[0]
        labels = [r.label for r in table.rows]
        assert any("Top" in l for l in labels)
        assert any("Bottom" in l for l in labels)

    def test_crosstab_table_has_segments(self):
        config = TableConfig(table_types=[TableType.CROSSTAB])
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=_variables(), config=config,
        )
        table = result.tables[0]
        assert len(table.rows) >= 2
        assert "Segment" in table.rows[0].label

    def test_table_has_variable_info(self):
        config = TableConfig(table_types=[TableType.FREQUENCY])
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=_variables(), config=config,
        )
        table = result.tables[0]
        assert table.variable_name == "SCR_01"
        assert table.question_id == "Q1"
        assert table.question_text == "Category usage?"

    def test_get_table_by_variable(self):
        config = TableConfig(table_types=[TableType.FREQUENCY])
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=_variables(), config=config,
        )
        table = result.get_table("ATT_01")
        assert table is not None
        assert table.variable_name == "ATT_01"

    def test_tables_by_type_filter(self):
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=_variables(),
        )
        freq = result.tables_by_type(TableType.FREQUENCY)
        assert len(freq) >= 3

    def test_custom_banner_variables(self):
        config = TableConfig(
            table_types=[TableType.FREQUENCY],
            banner_variables=["Gender", "Age Group", "Region"],
        )
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=_variables(), config=config,
        )
        table = result.tables[0]
        assert "Gender" in table.banner_columns
        assert "Age Group" in table.banner_columns
        assert "Total" in table.banner_columns

    def test_table_cells_have_base(self):
        config = TableConfig(table_types=[TableType.FREQUENCY])
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=_variables(), config=config,
        )
        table = result.tables[0]
        for row in table.rows:
            for col, cell in row.cells.items():
                assert cell.base > 0

    def test_frequency_table_has_base_row(self):
        config = TableConfig(table_types=[TableType.FREQUENCY])
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=_variables(), config=config,
        )
        table = result.tables[0]
        assert table.base_row is not None
        assert table.base_row.label == "Base"


# ---------------------------------------------------------------------------
# AC-2: Significance toggle is configurable
# ---------------------------------------------------------------------------

class TestSignificanceConfig:
    def test_significance_enabled_by_default(self):
        config = TableConfig()
        assert config.significance.enabled is True

    def test_significance_can_be_disabled(self):
        config = TableConfig(significance=SignificanceConfig(enabled=False))
        assert config.significance.enabled is False

    def test_sig_flags_present_when_enabled(self):
        config = TableConfig(
            table_types=[TableType.FREQUENCY],
            significance=SignificanceConfig(enabled=True),
        )
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=_variables(), config=config,
        )
        # At least one cell should have a sig_flag
        has_flag = any(
            cell.sig_flag is not None
            for t in result.tables
            for r in t.rows
            for cell in r.cells.values()
        )
        assert has_flag

    def test_no_sig_flags_when_disabled(self):
        config = TableConfig(
            table_types=[TableType.FREQUENCY],
            significance=SignificanceConfig(enabled=False),
        )
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=_variables(), config=config,
        )
        has_flag = any(
            cell.sig_flag is not None
            for t in result.tables
            for r in t.rows
            for cell in r.cells.values()
        )
        assert not has_flag

    def test_confidence_level_configurable(self):
        config = TableConfig(significance=SignificanceConfig(confidence_level=0.99))
        assert config.significance.confidence_level == 0.99

    def test_base_size_minimum_configurable(self):
        config = TableConfig(base_size_minimum=50)
        assert config.base_size_minimum == 50


# ---------------------------------------------------------------------------
# AC-3: Output artifacts stored under run folder
# ---------------------------------------------------------------------------

class TestRunProvenance:
    def test_run_has_id(self):
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=3,
            variables=_variables(),
        )
        assert result.run_id.startswith("tblrun-")

    def test_run_links_to_project(self):
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=3,
            variables=_variables(),
        )
        assert result.project_id == "proj-001"

    def test_run_links_to_mapping(self):
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=2, questionnaire_version=3,
            variables=_variables(),
        )
        assert result.mapping_id == "map-001"
        assert result.mapping_version == 2
        assert result.questionnaire_version == 3

    def test_provenance_dict(self):
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=_variables(),
        )
        prov = result.provenance()
        assert prov["run_id"] == result.run_id
        assert prov["project_id"] == "proj-001"
        assert prov["mapping_id"] == "map-001"
        assert prov["total_tables"] == result.total_tables
        assert "significance_enabled" in prov
        assert "created_at" in prov

    def test_table_ids_unique(self):
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=_variables(),
        )
        ids = [t.table_id for t in result.tables]
        assert len(ids) == len(set(ids))

    def test_created_at_set(self):
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=_variables(),
        )
        assert result.created_at is not None

    def test_config_stored_on_result(self):
        config = TableConfig(
            table_types=[TableType.FREQUENCY, TableType.MEAN],
            banner_variables=["Gender"],
            significance=SignificanceConfig(enabled=False),
        )
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=_variables(), config=config,
        )
        assert result.config.significance.enabled is False
        assert "Gender" in result.config.banner_variables

    def test_save_run_creates_folder(self, tmp_path: Path):
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=_variables(),
        )
        run_dir = save_run(result, tmp_path / "Runs")
        assert run_dir.is_dir()
        assert run_dir.name == result.run_id
        manifest = run_dir / "manifest.json"
        assert manifest.exists()

    def test_save_run_manifest_valid_json(self, tmp_path: Path):
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=_variables(),
        )
        run_dir = save_run(result, tmp_path / "Runs")
        manifest = run_dir / "manifest.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["run_id"] == result.run_id
        assert data["project_id"] == "proj-001"
        assert len(data["tables"]) == result.total_tables
