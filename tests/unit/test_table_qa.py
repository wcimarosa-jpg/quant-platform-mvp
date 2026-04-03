"""Tests for table QA checks (P06-02 hardened).

Uses real computed tables for QA validation.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from packages.survey_analysis.table_generator import (
    GeneratedTable,
    TableCell,
    TableConfig,
    TableRow,
    TableRunResult,
    TableType,
    generate_tables,
    save_run,
)
from packages.survey_analysis.table_qa import (
    ALL_CHECKS,
    QAFinding,
    QAReport,
    QASeverity,
    check_base_size,
    check_empty_table,
    check_missing_values,
    check_percentage_sum,
    check_suspicious_distribution,
    check_zero_base,
    run_table_qa,
    save_qa_report,
)


def _survey_df(n: int = 200) -> pd.DataFrame:
    rng = np.random.RandomState(42)
    return pd.DataFrame({
        "SCR_01": rng.choice([1, 2, 3, 4], size=n, p=[0.4, 0.3, 0.2, 0.1]),
        "ATT_01": rng.choice([1, 2, 3, 4, 5], size=n),
    })


def _variables() -> list[dict]:
    return [
        {"var_name": "SCR_01", "question_id": "Q1", "question_text": "Usage?"},
        {"var_name": "ATT_01", "question_id": "Q2", "question_text": "Attitudes?"},
    ]


def _run_result(**kwargs) -> TableRunResult:
    defaults = dict(
        project_id="proj-001", mapping_id="map-001",
        mapping_version=1, questionnaire_version=1,
        variables=_variables(), df=_survey_df(),
    )
    defaults.update(kwargs)
    return generate_tables(**defaults)


# Hand-crafted tables for targeted QA check testing

def _table_with_low_base() -> GeneratedTable:
    return GeneratedTable(
        table_type=TableType.FREQUENCY, variable_name="LOW_BASE_VAR",
        banner_columns=["Total", "Seg A"],
        rows=[TableRow(label="Option 1", cells={
            "Total": TableCell(value=50, base=200, pct=25.0),
            "Seg A": TableCell(value=5, base=10, pct=50.0),
        })],
        base_row=TableRow(label="Base", cells={
            "Total": TableCell(value=200, base=200),
            "Seg A": TableCell(value=10, base=10),
        }),
    )


def _table_with_zero_base() -> GeneratedTable:
    return GeneratedTable(
        table_type=TableType.FREQUENCY, variable_name="ZERO_BASE_VAR",
        banner_columns=["Total", "Empty Seg"],
        rows=[TableRow(label="Option 1", cells={
            "Total": TableCell(value=50, base=200, pct=25.0),
            "Empty Seg": TableCell(value=0, base=0, pct=0.0),
        })],
        base_row=TableRow(label="Base", cells={
            "Total": TableCell(value=200, base=200),
            "Empty Seg": TableCell(value=0, base=0),
        }),
    )


def _table_with_missing() -> GeneratedTable:
    return GeneratedTable(
        table_type=TableType.FREQUENCY, variable_name="MISSING_VAR",
        banner_columns=["Total"],
        rows=[TableRow(label="Option 1", cells={"Total": TableCell(value=None, base=100)})],
    )


def _table_with_bad_pcts() -> GeneratedTable:
    return GeneratedTable(
        table_type=TableType.FREQUENCY, variable_name="BAD_PCT_VAR",
        banner_columns=["Total"],
        rows=[
            TableRow(label="Opt 1", cells={"Total": TableCell(value=30, base=100, pct=30.0)}),
            TableRow(label="Opt 2", cells={"Total": TableCell(value=20, base=100, pct=20.0)}),
            TableRow(label="Opt 3", cells={"Total": TableCell(value=10, base=100, pct=10.0)}),
        ],
    )


def _table_with_uniform_dist() -> GeneratedTable:
    return GeneratedTable(
        table_type=TableType.FREQUENCY, variable_name="UNIFORM_VAR",
        banner_columns=["Total"],
        rows=[
            TableRow(label=f"Opt {i}", cells={"Total": TableCell(value=25, base=100, pct=25.0)})
            for i in range(4)
        ],
    )


# ---------------------------------------------------------------------------
# QA execution
# ---------------------------------------------------------------------------

class TestQAExecution:
    def test_run_qa_returns_report(self):
        result = _run_result()
        report = run_table_qa(result)
        assert isinstance(report, QAReport)
        assert report.run_id == result.run_id

    def test_checks_run_count(self):
        result = _run_result()
        report = run_table_qa(result)
        assert report.checks_run == len(result.tables) * len(ALL_CHECKS)

    def test_clean_data_passes(self):
        result = _run_result()
        report = run_table_qa(result)
        assert report.error_count == 0

    def test_low_base_detected(self):
        findings = check_base_size(_table_with_low_base(), minimum=30)
        assert len(findings) >= 1
        assert findings[0].severity == QASeverity.ERROR

    def test_base_row_also_checked(self):
        """base_row with low base should also be flagged."""
        findings = check_base_size(_table_with_low_base(), minimum=30)
        base_findings = [f for f in findings if f.row_label == "Base"]
        assert len(base_findings) >= 1

    def test_zero_base_detected(self):
        findings = check_zero_base(_table_with_zero_base())
        assert len(findings) >= 1

    def test_zero_base_in_base_row_detected(self):
        findings = check_zero_base(_table_with_zero_base())
        base_findings = [f for f in findings if f.row_label == "Base"]
        assert len(base_findings) >= 1

    def test_missing_values_detected(self):
        findings = check_missing_values(_table_with_missing())
        assert len(findings) >= 1

    def test_percentage_sum_detected(self):
        findings = check_percentage_sum(_table_with_bad_pcts())
        assert len(findings) >= 1

    def test_suspicious_distribution_detected(self):
        findings = check_suspicious_distribution(_table_with_uniform_dist())
        assert len(findings) >= 1

    def test_empty_table_detected(self):
        table = GeneratedTable(
            table_type=TableType.FREQUENCY, variable_name="EMPTY",
            banner_columns=["Total"], rows=[],
        )
        findings = check_empty_table(table)
        assert len(findings) == 1

    def test_multi_select_pct_sum_not_flagged(self):
        """Multi-select can exceed 100% — no percentage_sum finding expected."""
        table = GeneratedTable(
            table_type=TableType.MULTI_SELECT, variable_name="MS",
            banner_columns=["Total"],
            rows=[
                TableRow(label="A", cells={"Total": TableCell(value=60, base=100, pct=60.0)}),
                TableRow(label="B", cells={"Total": TableCell(value=80, base=100, pct=80.0)}),
            ],
        )
        findings = check_percentage_sum(table)
        assert len(findings) == 0


# ---------------------------------------------------------------------------
# Finding content
# ---------------------------------------------------------------------------

class TestFindingContent:
    def test_finding_has_severity_and_remediation(self):
        findings = check_base_size(_table_with_low_base(), 30)
        assert findings[0].severity in QASeverity
        assert len(findings[0].remediation) > 10

    def test_finding_has_table_reference(self):
        findings = check_base_size(_table_with_low_base(), 30)
        assert findings[0].table_id
        assert findings[0].variable_name == "LOW_BASE_VAR"

    def test_for_ui_output(self):
        result = _run_result()
        report = run_table_qa(result)
        ui = report.for_ui()
        assert isinstance(ui, list)
        for item in ui:
            assert "severity" in item
            assert "remediation" in item

    def test_passed_property(self):
        result = _run_result()
        report = run_table_qa(result)
        assert report.passed is True


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestReportPersistence:
    def test_save_qa_report(self, tmp_path: Path):
        result = _run_result()
        run_dir = save_run(result, tmp_path / "Runs")
        report = run_table_qa(result)
        qa_file = save_qa_report(report, run_dir)
        assert qa_file.exists()
        data = json.loads(qa_file.read_text())
        assert data["run_id"] == result.run_id

    def test_run_folder_has_both_artifacts(self, tmp_path: Path):
        result = _run_result()
        run_dir = save_run(result, tmp_path / "Runs")
        report = run_table_qa(result)
        save_qa_report(report, run_dir)
        names = {f.name for f in run_dir.iterdir()}
        assert "manifest.json" in names
        assert "qa_report.json" in names
