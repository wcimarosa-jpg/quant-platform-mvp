"""Table QA checks.

Runs quality checks on generated tables: base-size thresholds,
missing values, suspicious distributions. Produces a QA report
attached to the run artifacts.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .table_generator import (
    GeneratedTable,
    TableCell,
    TableConfig,
    TableRow,
    TableRunResult,
    TableType,
)


class QASeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class QAFinding(BaseModel):
    """One QA finding with table/cell reference and remediation hint."""

    finding_id: str = Field(default_factory=lambda: f"qaf-{uuid.uuid4().hex[:8]}")
    severity: QASeverity
    check_name: str
    table_id: str
    variable_name: str
    column: str | None = None
    row_label: str | None = None
    message: str
    remediation: str


class QAReport(BaseModel):
    """Complete QA report for a table run."""

    report_id: str = Field(default_factory=lambda: f"qar-{uuid.uuid4().hex[:8]}")
    run_id: str
    project_id: str
    findings: list[QAFinding] = Field(default_factory=list)
    checks_run: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == QASeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == QASeverity.WARNING)

    @property
    def passed(self) -> bool:
        return self.error_count == 0

    def errors(self) -> list[QAFinding]:
        return [f for f in self.findings if f.severity == QASeverity.ERROR]

    def warnings(self) -> list[QAFinding]:
        return [f for f in self.findings if f.severity == QASeverity.WARNING]

    def for_ui(self) -> list[dict[str, Any]]:
        return [
            {
                "finding_id": f.finding_id,
                "severity": f.severity.value,
                "check_name": f.check_name,
                "table_id": f.table_id,
                "variable_name": f.variable_name,
                "column": f.column,
                "row_label": f.row_label,
                "message": f.message,
                "remediation": f.remediation,
            }
            for f in self.findings
        ]


# ---------------------------------------------------------------------------
# Individual QA checks
# ---------------------------------------------------------------------------

def check_base_size(table: GeneratedTable, minimum: int) -> list[QAFinding]:
    """Flag cells where base size is below the minimum threshold.

    Also checks the base_row if present.
    """
    findings: list[QAFinding] = []
    all_rows = list(table.rows)
    if table.base_row:
        all_rows.append(table.base_row)
    for row in all_rows:
        for col_name, cell in row.cells.items():
            if cell.base < minimum and cell.base > 0:
                findings.append(QAFinding(
                    severity=QASeverity.ERROR,
                    check_name="base_size",
                    table_id=table.table_id,
                    variable_name=table.variable_name,
                    column=col_name,
                    row_label=row.label,
                    message=f"Base size {cell.base} is below minimum {minimum} in column '{col_name}', row '{row.label}'.",
                    remediation="Suppress this cell, merge with adjacent segments, or flag with a footnote.",
                ))
    return findings


def check_zero_base(table: GeneratedTable) -> list[QAFinding]:
    """Flag cells with zero base (empty segment). Also checks base_row."""
    findings: list[QAFinding] = []
    all_rows = list(table.rows)
    if table.base_row:
        all_rows.append(table.base_row)
    for row in all_rows:
        for col_name, cell in row.cells.items():
            if cell.base == 0:
                findings.append(QAFinding(
                    severity=QASeverity.ERROR,
                    check_name="zero_base",
                    table_id=table.table_id,
                    variable_name=table.variable_name,
                    column=col_name,
                    row_label=row.label,
                    message=f"Zero base in column '{col_name}', row '{row.label}'. No respondents in this cell.",
                    remediation="Remove this banner column or merge with another segment.",
                ))
    return findings


def check_missing_values(table: GeneratedTable) -> list[QAFinding]:
    """Flag cells where value is None."""
    findings: list[QAFinding] = []
    for row in table.rows:
        for col_name, cell in row.cells.items():
            if cell.value is None:
                findings.append(QAFinding(
                    severity=QASeverity.WARNING,
                    check_name="missing_value",
                    table_id=table.table_id,
                    variable_name=table.variable_name,
                    column=col_name,
                    row_label=row.label,
                    message=f"Missing value in column '{col_name}', row '{row.label}'.",
                    remediation="Check data mapping for this variable. Value may not have been computed.",
                ))
    return findings


def check_percentage_sum(table: GeneratedTable) -> list[QAFinding]:
    """Flag columns where percentage values don't sum to ~100% for frequency tables."""
    if table.table_type not in (TableType.FREQUENCY, TableType.MULTI_SELECT):
        return []
    findings: list[QAFinding] = []
    for col_name in table.banner_columns:
        pct_sum = sum(
            row.cells.get(col_name, TableCell()).pct or 0.0
            for row in table.rows
        )
        if table.table_type == TableType.FREQUENCY and abs(pct_sum - 100.0) > 5.0 and pct_sum > 0:
            findings.append(QAFinding(
                severity=QASeverity.WARNING,
                check_name="percentage_sum",
                table_id=table.table_id,
                variable_name=table.variable_name,
                column=col_name,
                message=f"Percentages in column '{col_name}' sum to {pct_sum:.1f}%, expected ~100%.",
                remediation="Check for missing response codes or rounding issues.",
            ))
    return findings


def check_suspicious_distribution(table: GeneratedTable) -> list[QAFinding]:
    """Flag columns where all rows have identical percentages (possible data error)."""
    if table.table_type not in (TableType.FREQUENCY, TableType.CROSSTAB):
        return []
    findings: list[QAFinding] = []
    for col_name in table.banner_columns:
        pcts = [
            row.cells.get(col_name, TableCell()).pct
            for row in table.rows
            if row.cells.get(col_name, TableCell()).pct is not None
        ]
        if len(pcts) >= 3 and len(set(pcts)) == 1:
            findings.append(QAFinding(
                severity=QASeverity.WARNING,
                check_name="suspicious_distribution",
                table_id=table.table_id,
                variable_name=table.variable_name,
                column=col_name,
                message=f"All {len(pcts)} rows in column '{col_name}' have identical percentage ({pcts[0]:.1f}%). Possible data error.",
                remediation="Verify the data mapping and source data for this variable.",
            ))
    return findings


def check_empty_table(table: GeneratedTable) -> list[QAFinding]:
    """Flag tables with no rows."""
    if len(table.rows) == 0:
        return [QAFinding(
            severity=QASeverity.ERROR,
            check_name="empty_table",
            table_id=table.table_id,
            variable_name=table.variable_name,
            message="Table has no data rows.",
            remediation="Check that the variable is correctly mapped and has response data.",
        )]
    return []


ALL_CHECKS = [
    check_base_size,
    check_zero_base,
    check_missing_values,
    check_percentage_sum,
    check_suspicious_distribution,
    check_empty_table,
]


# ---------------------------------------------------------------------------
# Main QA pipeline
# ---------------------------------------------------------------------------

def run_table_qa(result: TableRunResult) -> QAReport:
    """Run all QA checks on a table run result.

    Returns a QAReport attached to the run.
    """
    report = QAReport(
        run_id=result.run_id,
        project_id=result.project_id,
    )

    minimum_base = result.config.base_size_minimum

    # Separate check_base_size (needs extra param) from standard checks
    _STANDARD_CHECKS = [c for c in ALL_CHECKS if c is not check_base_size]

    for table in result.tables:
        report.findings.extend(check_base_size(table, minimum_base))
        report.checks_run += 1

        for check_fn in _STANDARD_CHECKS:
            report.findings.extend(check_fn(table))
            report.checks_run += 1

    return report


# ---------------------------------------------------------------------------
# Persistence — save QA report alongside run artifacts
# ---------------------------------------------------------------------------

def save_qa_report(report: QAReport, run_dir: str | Path) -> Path:
    """Save the QA report as JSON in the run folder."""
    run_path = Path(run_dir)
    run_path.mkdir(parents=True, exist_ok=True)
    qa_file = run_path / "qa_report.json"
    data = report.model_dump(mode="json")
    qa_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return qa_file
