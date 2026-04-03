"""Tests for core table generation pipeline (P06-01 hardened).

Tables are now computed from real DataFrames — no stubs.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from packages.survey_analysis.table_generator import (
    GeneratedTable,
    SignificanceConfig,
    TableCell,
    TableConfig,
    TableGenerationError,
    TableRow,
    TableRunResult,
    TableType,
    generate_tables,
    save_run,
)


# ---------------------------------------------------------------------------
# Realistic fixture data
# ---------------------------------------------------------------------------

def _survey_df(n: int = 200) -> pd.DataFrame:
    rng = np.random.RandomState(42)
    return pd.DataFrame({
        "SCR_01": rng.choice([1, 2, 3, 4], size=n, p=[0.4, 0.3, 0.2, 0.1]),
        "ATT_01": rng.choice([1, 2, 3, 4, 5], size=n),
        "SAT_01": rng.choice([1, 2, 3, 4, 5], size=n, p=[0.05, 0.1, 0.2, 0.35, 0.3]),
        "GENDER": rng.choice([1, 2], size=n),
        "REGION": rng.choice([1, 2, 3], size=n),
        # Multi-select binary columns
        "MS_r1": rng.choice([0, 1], size=n, p=[0.4, 0.6]),
        "MS_r2": rng.choice([0, 1], size=n, p=[0.7, 0.3]),
        "MS_r3": rng.choice([0, 1], size=n, p=[0.5, 0.5]),
    })


def _variables() -> list[dict]:
    return [
        {"var_name": "SCR_01", "question_id": "Q1", "question_text": "Category usage?",
         "value_labels": {1: "Daily", 2: "Weekly", 3: "Monthly", 4: "Rarely"}},
        {"var_name": "ATT_01", "question_id": "Q2", "question_text": "I research products"},
        {"var_name": "SAT_01", "question_id": "Q3", "question_text": "Overall satisfaction",
         "t2b_codes": [4, 5], "b2b_codes": [1, 2]},
    ]


def _run(**kw) -> TableRunResult:
    defaults = dict(
        project_id="proj-001", mapping_id="map-001",
        mapping_version=1, questionnaire_version=1,
        variables=_variables(), df=_survey_df(),
    )
    defaults.update(kw)
    return generate_tables(**defaults)


# ---------------------------------------------------------------------------
# Frequency tables — data-driven
# ---------------------------------------------------------------------------

class TestFrequencyTable:
    def test_frequency_row_count_matches_unique_codes(self):
        df = _survey_df()
        config = TableConfig(table_types=[TableType.FREQUENCY])
        result = _run(config=config)
        tbl = result.get_table("SCR_01")
        assert tbl is not None
        assert len(tbl.rows) == df["SCR_01"].nunique()

    def test_frequency_percentages_sum_to_100(self):
        config = TableConfig(table_types=[TableType.FREQUENCY])
        result = _run(config=config)
        tbl = result.get_table("SCR_01")
        pct_sum = sum(r.cells["Total"].pct for r in tbl.rows)
        assert abs(pct_sum - 100.0) < 1.0

    def test_frequency_uses_value_labels(self):
        config = TableConfig(table_types=[TableType.FREQUENCY])
        result = _run(config=config)
        tbl = result.get_table("SCR_01")
        labels = [r.label for r in tbl.rows]
        assert "Daily" in labels
        assert "Weekly" in labels

    def test_frequency_base_row_present(self):
        config = TableConfig(table_types=[TableType.FREQUENCY])
        result = _run(config=config)
        tbl = result.get_table("SCR_01")
        assert tbl.base_row is not None
        assert tbl.base_row.cells["Total"].base == 200

    def test_frequency_counts_are_data_driven(self):
        df = _survey_df()
        config = TableConfig(table_types=[TableType.FREQUENCY])
        result = _run(df=df, config=config)
        tbl = result.get_table("SCR_01")
        expected_daily = int((df["SCR_01"] == 1).sum())
        daily_row = next(r for r in tbl.rows if r.code == 1)
        assert daily_row.cells["Total"].value == expected_daily


# ---------------------------------------------------------------------------
# Mean tables
# ---------------------------------------------------------------------------

class TestMeanTable:
    def test_mean_computed_from_data(self):
        df = _survey_df()
        config = TableConfig(table_types=[TableType.MEAN])
        result = _run(df=df, config=config)
        tbl = result.get_table("ATT_01")
        mean_row = next(r for r in tbl.rows if r.label == "Mean")
        expected = round(df["ATT_01"].mean(), 2)
        assert mean_row.cells["Total"].value == expected

    def test_stddev_computed_from_data(self):
        df = _survey_df()
        config = TableConfig(table_types=[TableType.MEAN])
        result = _run(df=df, config=config)
        tbl = result.get_table("ATT_01")
        std_row = next(r for r in tbl.rows if r.label == "Std Dev")
        expected = round(df["ATT_01"].std(), 2)
        assert std_row.cells["Total"].value == expected


# ---------------------------------------------------------------------------
# T2B tables
# ---------------------------------------------------------------------------

class TestT2BTable:
    def test_t2b_uses_provided_codes(self):
        df = _survey_df()
        config = TableConfig(table_types=[TableType.TOP2BOX])
        result = _run(df=df, config=config)
        tbl = result.get_table("SAT_01")
        t2b_row = next(r for r in tbl.rows if "Top" in r.label)
        expected_count = int(df["SAT_01"].isin([4, 5]).sum())
        assert t2b_row.cells["Total"].value == expected_count

    def test_b2b_computed(self):
        df = _survey_df()
        config = TableConfig(table_types=[TableType.TOP2BOX])
        result = _run(df=df, config=config)
        tbl = result.get_table("SAT_01")
        b2b_row = next(r for r in tbl.rows if "Bottom" in r.label)
        expected = int(df["SAT_01"].isin([1, 2]).sum())
        assert b2b_row.cells["Total"].value == expected


# ---------------------------------------------------------------------------
# Multi-select tables
# ---------------------------------------------------------------------------

class TestMultiSelectTable:
    def test_multi_select_with_item_columns(self):
        df = _survey_df()
        config = TableConfig(table_types=[TableType.MULTI_SELECT])
        ms_var = {
            "var_name": "MS",
            "question_id": "Q4",
            "item_columns": ["MS_r1", "MS_r2", "MS_r3"],
            "item_labels": {"MS_r1": "Instagram", "MS_r2": "TikTok", "MS_r3": "YouTube"},
        }
        result = generate_tables(
            project_id="proj-001", mapping_id="map-001",
            mapping_version=1, questionnaire_version=1,
            variables=[ms_var], df=df, config=config,
        )
        tbl = result.tables[0]
        assert tbl.table_type == TableType.MULTI_SELECT
        assert len(tbl.rows) == 3
        labels = [r.label for r in tbl.rows]
        assert "Instagram" in labels

    def test_multi_select_counts_are_real(self):
        df = _survey_df()
        config = TableConfig(table_types=[TableType.MULTI_SELECT])
        ms_var = {"var_name": "MS", "item_columns": ["MS_r1"]}
        result = generate_tables(
            project_id="p", mapping_id="m", mapping_version=1,
            questionnaire_version=1, variables=[ms_var], df=df, config=config,
        )
        expected = int(df["MS_r1"].sum())
        assert result.tables[0].rows[0].cells["Total"].value == expected


# ---------------------------------------------------------------------------
# Crosstab tables
# ---------------------------------------------------------------------------

class TestCrosstabTable:
    def test_crosstab_rows_match_codes(self):
        df = _survey_df()
        config = TableConfig(table_types=[TableType.CROSSTAB])
        result = _run(df=df, config=config)
        tbl = result.get_table("SCR_01")
        assert len(tbl.rows) == df["SCR_01"].nunique()


# ---------------------------------------------------------------------------
# Banner splits
# ---------------------------------------------------------------------------

class TestBannerSplits:
    def test_banner_produces_split_columns(self):
        config = TableConfig(
            table_types=[TableType.FREQUENCY],
            banner_variables=["GENDER"],
        )
        result = _run(config=config)
        tbl = result.get_table("SCR_01")
        assert "Total" in tbl.banner_columns
        assert any("GENDER:" in c for c in tbl.banner_columns)

    def test_banner_bases_are_correct(self):
        df = _survey_df()
        config = TableConfig(
            table_types=[TableType.FREQUENCY],
            banner_variables=["GENDER"],
        )
        result = _run(df=df, config=config)
        tbl = result.get_table("SCR_01")
        gender1_col = next(c for c in tbl.banner_columns if "GENDER:1" in c)
        expected_base = int((df["GENDER"] == 1).sum())
        assert tbl.base_row.cells[gender1_col].base == expected_base


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_empty_df_raises(self):
        with pytest.raises(TableGenerationError, match="empty"):
            generate_tables(
                project_id="p", mapping_id="m", mapping_version=1,
                questionnaire_version=1, variables=_variables(),
                df=pd.DataFrame(),
            )

    def test_missing_variable_raises(self):
        df = _survey_df()
        with pytest.raises(TableGenerationError, match="not found"):
            generate_tables(
                project_id="p", mapping_id="m", mapping_version=1,
                questionnaire_version=1,
                variables=[{"var_name": "NONEXISTENT"}],
                df=df, config=TableConfig(table_types=[TableType.FREQUENCY]),
            )


# ---------------------------------------------------------------------------
# Provenance and persistence
# ---------------------------------------------------------------------------

class TestProvenance:
    def test_provenance_fields(self):
        result = _run()
        prov = result.provenance()
        assert prov["project_id"] == "proj-001"
        assert prov["mapping_id"] == "map-001"
        assert prov["total_tables"] > 0

    def test_save_run(self, tmp_path: Path):
        result = _run()
        run_dir = save_run(result, tmp_path / "Runs")
        manifest = run_dir / "manifest.json"
        assert manifest.exists()
        data = json.loads(manifest.read_text())
        assert data["run_id"] == result.run_id

    def test_table_ids_unique(self):
        result = _run()
        ids = [t.table_id for t in result.tables]
        assert len(ids) == len(set(ids))
