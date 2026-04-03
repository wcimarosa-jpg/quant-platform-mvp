"""Core table generation pipeline.

Generates frequency, multi-select, T2B, mean, and segment crosstab
tables from a mapping config and data. Output artifacts stored with
run provenance.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TableType(str, Enum):
    FREQUENCY = "frequency"
    MULTI_SELECT = "multi_select"
    TOP2BOX = "top2box"
    MEAN = "mean"
    CROSSTAB = "crosstab"


class SignificanceConfig(BaseModel):
    """Significance testing configuration."""

    enabled: bool = True
    confidence_level: float = 0.95  # 90%, 95%, or 99%
    method: str = "chi_square"      # chi_square, z_test, t_test


class TableConfig(BaseModel):
    """Configuration for a table generation run."""

    table_types: list[TableType] = Field(default_factory=lambda: list(TableType))
    banner_variables: list[str] = Field(default_factory=list)
    significance: SignificanceConfig = Field(default_factory=SignificanceConfig)
    base_size_minimum: int = 30


class TableCell(BaseModel):
    """One cell in a generated table."""

    value: float | int | str | None = None
    base: int = 0
    pct: float | None = None
    sig_flag: str | None = None  # e.g., "A", "B" for column letter significance


class TableRow(BaseModel):
    """One row in a generated table."""

    label: str
    code: int | None = None
    cells: dict[str, TableCell] = Field(default_factory=dict)  # keyed by banner column


class GeneratedTable(BaseModel):
    """One generated output table."""

    table_id: str = Field(default_factory=lambda: f"tbl-{uuid.uuid4().hex[:8]}")
    table_type: TableType
    variable_name: str
    question_id: str | None = None
    question_text: str | None = None
    banner_columns: list[str]
    rows: list[TableRow]
    base_row: TableRow | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TableRunResult(BaseModel):
    """Complete result of a table generation run."""

    run_id: str = Field(default_factory=lambda: f"tblrun-{uuid.uuid4().hex[:8]}")
    project_id: str
    mapping_id: str
    mapping_version: int
    questionnaire_version: int
    config: TableConfig
    tables: list[GeneratedTable]
    total_tables: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def model_post_init(self, __context: Any) -> None:
        self.total_tables = len(self.tables)

    def get_table(self, variable_name: str) -> GeneratedTable | None:
        for t in self.tables:
            if t.variable_name == variable_name:
                return t
        return None

    def tables_by_type(self, table_type: TableType) -> list[GeneratedTable]:
        return [t for t in self.tables if t.table_type == table_type]

    def provenance(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "project_id": self.project_id,
            "mapping_id": self.mapping_id,
            "mapping_version": self.mapping_version,
            "questionnaire_version": self.questionnaire_version,
            "total_tables": self.total_tables,
            "significance_enabled": self.config.significance.enabled,
            "created_at": self.created_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Table generators — STUB implementations with hardcoded values.
# TODO: Replace with real computation from DataFrame + mapping config
# when the data processing layer is connected.
# ---------------------------------------------------------------------------

def _gen_frequency_table(
    var_name: str,
    question_id: str | None,
    question_text: str | None,
    banner_cols: list[str],
    sig_enabled: bool,
) -> GeneratedTable:
    """Generate a frequency table stub."""
    rows = [
        TableRow(
            label=f"Option {i+1}", code=i+1,
            cells={
                "Total": TableCell(value=100, base=200, pct=50.0),
                **{
                    col: TableCell(
                        value=50, base=100, pct=50.0,
                        sig_flag="A" if sig_enabled and i == 0 else None,
                    )
                    for col in banner_cols
                },
            },
        )
        for i in range(4)
    ]
    base_row = TableRow(
        label="Base", cells={
            "Total": TableCell(value=200, base=200),
            **{col: TableCell(value=100, base=100) for col in banner_cols},
        },
    )
    return GeneratedTable(
        table_type=TableType.FREQUENCY,
        variable_name=var_name,
        question_id=question_id,
        question_text=question_text,
        banner_columns=["Total"] + banner_cols,
        rows=rows,
        base_row=base_row,
    )


def _gen_mean_table(
    var_name: str,
    question_id: str | None,
    question_text: str | None,
    banner_cols: list[str],
    sig_enabled: bool,
) -> GeneratedTable:
    """Generate a mean table stub."""
    rows = [
        TableRow(
            label="Mean", cells={
                "Total": TableCell(value=3.5, base=200),
                **{col: TableCell(value=3.5, base=100) for col in banner_cols},
            },
        ),
        TableRow(
            label="Std Dev", cells={
                "Total": TableCell(value=1.2, base=200),
                **{col: TableCell(value=1.2, base=100) for col in banner_cols},
            },
        ),
    ]
    return GeneratedTable(
        table_type=TableType.MEAN,
        variable_name=var_name,
        question_id=question_id,
        question_text=question_text,
        banner_columns=["Total"] + banner_cols,
        rows=rows,
    )


def _gen_t2b_table(
    var_name: str,
    question_id: str | None,
    question_text: str | None,
    banner_cols: list[str],
    sig_enabled: bool,
) -> GeneratedTable:
    """Generate a Top-2-Box table stub."""
    rows = [
        TableRow(
            label="Top-2-Box (%)", cells={
                "Total": TableCell(value=65.0, base=200, pct=65.0),
                **{col: TableCell(value=65.0, base=100, pct=65.0) for col in banner_cols},
            },
        ),
        TableRow(
            label="Bottom-2-Box (%)", cells={
                "Total": TableCell(value=15.0, base=200, pct=15.0),
                **{col: TableCell(value=15.0, base=100, pct=15.0) for col in banner_cols},
            },
        ),
    ]
    return GeneratedTable(
        table_type=TableType.TOP2BOX,
        variable_name=var_name,
        question_id=question_id,
        question_text=question_text,
        banner_columns=["Total"] + banner_cols,
        rows=rows,
    )


def _gen_crosstab_table(
    var_name: str,
    question_id: str | None,
    question_text: str | None,
    banner_cols: list[str],
    sig_enabled: bool,
) -> GeneratedTable:
    """Generate a segment crosstab table stub."""
    rows = [
        TableRow(
            label=f"Segment {i+1}", code=i+1,
            cells={
                "Total": TableCell(value=50, base=200, pct=25.0),
                **{col: TableCell(value=25, base=100, pct=25.0) for col in banner_cols},
            },
        )
        for i in range(4)
    ]
    return GeneratedTable(
        table_type=TableType.CROSSTAB,
        variable_name=var_name,
        question_id=question_id,
        question_text=question_text,
        banner_columns=["Total"] + banner_cols,
        rows=rows,
    )


_TABLE_GENERATORS = {
    TableType.FREQUENCY: _gen_frequency_table,
    TableType.MULTI_SELECT: _gen_frequency_table,  # same structure
    TableType.TOP2BOX: _gen_t2b_table,
    TableType.MEAN: _gen_mean_table,
    TableType.CROSSTAB: _gen_crosstab_table,
}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def generate_tables(
    project_id: str,
    mapping_id: str,
    mapping_version: int,
    questionnaire_version: int,
    variables: list[dict[str, str]],
    config: TableConfig | None = None,
) -> TableRunResult:
    """Generate all configured table types for each mapped variable.

    Args:
        project_id: Project identifier.
        mapping_id: Mapping version identifier.
        mapping_version: Mapping version number.
        questionnaire_version: Questionnaire version number.
        variables: List of {"var_name": ..., "question_id": ..., "question_text": ...}.
        config: Optional table configuration. Defaults to all types.

    Returns:
        TableRunResult with all generated tables and provenance.
    """
    if config is None:
        config = TableConfig()

    banner_cols = config.banner_variables if config.banner_variables else ["Segment A", "Segment B"]
    sig = config.significance.enabled
    tables: list[GeneratedTable] = []

    for var_info in variables:
        var_name = var_info["var_name"]
        qid = var_info.get("question_id")
        qtext = var_info.get("question_text")

        for table_type in config.table_types:
            gen = _TABLE_GENERATORS.get(table_type)
            if gen:
                tables.append(gen(var_name, qid, qtext, banner_cols, sig))

    return TableRunResult(
        project_id=project_id,
        mapping_id=mapping_id,
        mapping_version=mapping_version,
        questionnaire_version=questionnaire_version,
        config=config,
        tables=tables,
    )


# ---------------------------------------------------------------------------
# Run persistence — save to disk under a run folder
# ---------------------------------------------------------------------------

def save_run(result: TableRunResult, base_dir: str | Path) -> Path:
    """Serialize a TableRunResult to a run-specific subfolder.

    Creates ``base_dir / result.run_id / manifest.json`` with the full
    result serialized as JSON.

    Returns the path to the run folder.
    """
    run_dir = Path(base_dir) / result.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = run_dir / "manifest.json"
    data = result.model_dump(mode="json")
    manifest.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    return run_dir
