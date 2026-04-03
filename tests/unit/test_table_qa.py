"""Contract tests for table QA checks (P06-02).

AC-1: QA checks run automatically after table generation.
AC-2: Findings include severity and remediation hint.
AC-3: QA report is attached to run artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path

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


def _variables() -> list[dict[str, str]]:
    return [
        {"var_name": "SCR_01", "question_id": "Q1", "question_text": "Usage?"},
        {"var_name": "ATT_01", "question_id": "Q2", "question_text": "Attitudes?"},
    ]


def _run_result(**kwargs) -> TableRunResult:
    defaults = dict(
        project_id="proj-001", mapping_id="map-001",
        mapping_version=1, questionnaire_version=1,
        variables=_variables(),
    )
    defaults.update(kwargs)
    return generate_tables(**defaults)


def _table_with_low_base() -> GeneratedTable:
    return GeneratedTable(
        table_type=TableType.FREQUENCY,
        variable_name="LOW_BASE_VAR",
        banner_columns=["Total", "Seg A"],
        rows=[
            TableRow(label="Option 1", cells={
                "Total": TableCell(value=50, base=200, pct=25.0),
                "Seg A": TableCell(value=5, base=10, pct=50.0),  # base=10 < 30
            }),
        ],
    )


def _table_with_zero_base() -> GeneratedTable:
    return GeneratedTable(
        table_type=TableType.FREQUENCY,
        variable_name="ZERO_BASE_VAR",
        banner_columns=["Total", "Empty Seg"],
        rows=[
            TableRow(label="Option 1", cells={
                "Total": TableCell(value=50, base=200, pct=25.0),
                "Empty Seg": TableCell(value=0, base=0, pct=0.0),
            }),
        ],
    )


def _table_with_missing() -> GeneratedTable:
    return GeneratedTable(
        table_type=TableType.FREQUENCY,
        variable_name="MISSING_VAR",
        banner_columns=["Total"],
        rows=[
            TableRow(label="Option 1", cells={
                "Total": TableCell(value=None, base=100),
            }),
        ],
    )


def _table_with_bad_pcts() -> GeneratedTable:
    return GeneratedTable(
        table_type=TableType.FREQUENCY,
        variable_name="BAD_PCT_VAR",
        banner_columns=["Total"],
        rows=[
            TableRow(label="Opt 1", cells={"Total": TableCell(value=30, base=100, pct=30.0)}),
            TableRow(label="Opt 2", cells={"Total": TableCell(value=20, base=100, pct=20.0)}),
            TableRow(label="Opt 3", cells={"Total": TableCell(value=10, base=100, pct=10.0)}),
            # sums to 60%, not 100%
        ],
    )


def _table_with_uniform_dist() -> GeneratedTable:
    return GeneratedTable(
        table_type=TableType.FREQUENCY,
        variable_name="UNIFORM_VAR",
        banner_columns=["Total"],
        rows=[
            TableRow(label="Opt 1", cells={"Total": TableCell(value=25, base=100, pct=25.0)}),
            TableRow(label="Opt 2", cells={"Total": TableCell(value=25, base=100, pct=25.0)}),
            TableRow(label="Opt 3", cells={"Total": TableCell(value=25, base=100, pct=25.0)}),
            TableRow(label="Opt 4", cells={"Total": TableCell(value=25, base=100, pct=25.0)}),
        ],
    )


# ---------------------------------------------------------------------------
# AC-1: QA checks run automatically after table generation
# ---------------------------------------------------------------------------

class TestQAExecution:
    def test_run_qa_returns_report(self):
        result = _run_result()
        report = run_table_qa(result)
        assert isinstance(report, QAReport)
        assert report.run_id == result.run_id
        assert report.project_id == result.project_id

    def test_checks_run_count(self):
        result = _run_result()
        report = run_table_qa(result)
        assert report.checks_run > 0
        # Each table gets len(ALL_CHECKS) checks
        assert report.checks_run == len(result.tables) * len(ALL_CHECKS)

    def test_clean_tables_pass(self):
        result = _run_result()
        report = run_table_qa(result)
        # Generated stub tables have base=200/100, valid data — should mostly pass
        # (suspicious_distribution will flag uniform stubs, that's expected)
        assert report.error_count == 0

    def test_low_base_detected(self):
        findings = check_base_size(_table_with_low_base(), minimum=30)
        assert len(findings) >= 1
        assert findings[0].severity == QASeverity.ERROR
        assert findings[0].check_name == "base_size"

    def test_zero_base_detected(self):
        findings = check_zero_base(_table_with_zero_base())
        assert len(findings) >= 1
        assert findings[0].severity == QASeverity.ERROR
        assert findings[0].check_name == "zero_base"

    def test_missing_values_detected(self):
        findings = check_missing_values(_table_with_missing())
        assert len(findings) >= 1
        assert findings[0].severity == QASeverity.WARNING

    def test_percentage_sum_detected(self):
        findings = check_percentage_sum(_table_with_bad_pcts())
        assert len(findings) >= 1
        assert findings[0].check_name == "percentage_sum"

    def test_suspicious_distribution_detected(self):
        findings = check_suspicious_distribution(_table_with_uniform_dist())
        assert len(findings) >= 1
        assert findings[0].check_name == "suspicious_distribution"

    def test_empty_table_detected(self):
        table = GeneratedTable(
            table_type=TableType.FREQUENCY, variable_name="EMPTY",
            banner_columns=["Total"], rows=[],
        )
        findings = check_empty_table(table)
        assert len(findings) == 1
        assert findings[0].severity == QASeverity.ERROR


# ---------------------------------------------------------------------------
# AC-2: Findings include severity and remediation hint
# ---------------------------------------------------------------------------

class TestFindingContent:
    def test_finding_has_severity(self):
        findings = check_base_size(_table_with_low_base(), 30)
        assert findings[0].severity in QASeverity

    def test_finding_has_remediation(self):
        findings = check_base_size(_table_with_low_base(), 30)
        assert findings[0].remediation
        assert len(findings[0].remediation) > 10

    def test_finding_has_table_reference(self):
        findings = check_base_size(_table_with_low_base(), 30)
        assert findings[0].table_id
        assert findings[0].variable_name == "LOW_BASE_VAR"

    def test_finding_has_cell_reference(self):
        findings = check_base_size(_table_with_low_base(), 30)
        assert findings[0].column == "Seg A"
        assert findings[0].row_label == "Option 1"

    def test_finding_message_is_specific(self):
        findings = check_base_size(_table_with_low_base(), 30)
        msg = findings[0].message
        assert "10" in msg  # actual base
        assert "30" in msg  # minimum

    def test_finding_ids_unique(self):
        result = _run_result()
        report = run_table_qa(result)
        ids = [f.finding_id for f in report.findings]
        assert len(ids) == len(set(ids))

    def test_for_ui_output(self):
        result = _run_result()
        report = run_table_qa(result)
        ui = report.for_ui()
        assert isinstance(ui, list)
        for item in ui:
            assert "finding_id" in item
            assert "severity" in item
            assert "message" in item
            assert "remediation" in item
            assert "table_id" in item

    def test_passed_property(self):
        result = _run_result()
        report = run_table_qa(result)
        assert report.passed is True  # clean stubs should pass

    def test_error_and_warning_counts(self):
        result = _run_result()
        report = run_table_qa(result)
        assert report.error_count + report.warning_count == len(report.findings)


# ---------------------------------------------------------------------------
# AC-3: QA report attached to run artifacts
# ---------------------------------------------------------------------------

class TestReportPersistence:
    def test_report_links_to_run(self):
        result = _run_result()
        report = run_table_qa(result)
        assert report.run_id == result.run_id

    def test_save_qa_report_to_run_folder(self, tmp_path: Path):
        result = _run_result()
        run_dir = save_run(result, tmp_path / "Runs")
        report = run_table_qa(result)
        qa_file = save_qa_report(report, run_dir)
        assert qa_file.exists()
        assert qa_file.name == "qa_report.json"

    def test_saved_report_is_valid_json(self, tmp_path: Path):
        result = _run_result()
        run_dir = save_run(result, tmp_path / "Runs")
        report = run_table_qa(result)
        qa_file = save_qa_report(report, run_dir)
        data = json.loads(qa_file.read_text(encoding="utf-8"))
        assert data["run_id"] == result.run_id
        assert data["project_id"] == result.project_id
        assert isinstance(data["findings"], list)

    def test_run_folder_contains_both_artifacts(self, tmp_path: Path):
        result = _run_result()
        run_dir = save_run(result, tmp_path / "Runs")
        report = run_table_qa(result)
        save_qa_report(report, run_dir)
        files = list(run_dir.iterdir())
        names = {f.name for f in files}
        assert "manifest.json" in names
        assert "qa_report.json" in names

    def test_report_has_created_at(self):
        result = _run_result()
        report = run_table_qa(result)
        assert report.created_at is not None
