"""Core table generation pipeline.

Computes frequency, multi-select, T2B, mean, and segment crosstab
tables from a pandas DataFrame and mapping configuration. Output
artifacts stored with run provenance.

Input assumptions:
- ``df``: pandas DataFrame with one row per respondent.
- ``variables``: list of dicts with at least ``var_name`` (column in df).
  Optional keys: ``question_id``, ``question_text``, ``value_labels``
  (dict[int, str]), ``t2b_codes`` (list[int] for top-box), ``b2b_codes``,
  ``item_columns`` (list[str] for multi-select binary columns),
  ``item_labels`` (dict[str, str]).
- ``banner_variables``: column names in df whose unique values define the
  banner splits.  If empty, only a "Total" column is produced.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd
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
    confidence_level: float = 0.95
    method: str = "chi_square"


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
    sig_flag: str | None = None


class TableRow(BaseModel):
    """One row in a generated table."""

    label: str
    code: int | None = None
    cells: dict[str, TableCell] = Field(default_factory=dict)


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
            "significance_configured": self.config.significance.enabled,
            # TODO: Actual significance computation (chi-square/z-test) not yet
            # implemented. This flag reflects config intent, not computed flags.
            "significance_computed": False,
            "created_at": self.created_at.isoformat(),
        }


class TableGenerationError(Exception):
    """Raised when table generation fails due to invalid inputs."""


# ---------------------------------------------------------------------------
# Banner helpers
# ---------------------------------------------------------------------------

def _banner_splits(df: pd.DataFrame, banner_cols: list[str]) -> dict[str, pd.DataFrame]:
    """Return {"Total": full_df, "col:val_1": subset, ...}."""
    splits: dict[str, pd.DataFrame] = {"Total": df}
    for col in banner_cols:
        if col not in df.columns:
            continue
        for val in sorted(df[col].dropna().unique()):
            splits[f"{col}:{val}"] = df[df[col] == val]
    return splits


# ---------------------------------------------------------------------------
# Real table generators — computed from DataFrame
#
# Note: the ``sig`` parameter is reserved for future significance testing
# (chi-square, z-test). Currently unused — all sig_flag fields remain None.
# ---------------------------------------------------------------------------

def _gen_frequency(
    df: pd.DataFrame, var: dict[str, Any], splits: dict[str, pd.DataFrame], sig: bool,
) -> GeneratedTable:
    """Frequency distribution for a single-select variable."""
    var_name = var["var_name"]
    # Coerce keys to int — JSON payloads always have string keys
    value_labels: dict[int, str] = {int(k): v for k, v in var.get("value_labels", {}).items()}
    if var_name not in df.columns:
        raise TableGenerationError(f"Variable '{var_name}' not found in data.")

    codes = sorted(df[var_name].dropna().unique())
    rows: list[TableRow] = []
    for code in codes:
        label = value_labels.get(int(code), f"Code {int(code)}")
        cells: dict[str, TableCell] = {}
        for split_name, split_df in splits.items():
            col = split_df[var_name].dropna()
            count = int((col == code).sum())
            base = len(col)
            pct = round(count / base * 100, 1) if base > 0 else 0.0
            cells[split_name] = TableCell(value=count, base=base, pct=pct)
        rows.append(TableRow(label=label, code=int(code), cells=cells))

    base_cells: dict[str, TableCell] = {}
    for split_name, split_df in splits.items():
        n = int(split_df[var_name].notna().sum())
        base_cells[split_name] = TableCell(value=n, base=n)

    return GeneratedTable(
        table_type=TableType.FREQUENCY,
        variable_name=var_name,
        question_id=var.get("question_id"),
        question_text=var.get("question_text"),
        banner_columns=list(splits.keys()),
        rows=rows,
        base_row=TableRow(label="Base", cells=base_cells),
    )


def _gen_multi_select(
    df: pd.DataFrame, var: dict[str, Any], splits: dict[str, pd.DataFrame], sig: bool,
) -> GeneratedTable:
    """Multi-select: expects binary (0/1) columns listed in ``var["item_columns"]``.

    Falls back to frequency if item_columns is absent.
    """
    item_cols: list[str] = var.get("item_columns", [])
    item_labels: dict[str, str] = var.get("item_labels", {})
    if not item_cols:
        return _gen_frequency(df, var, splits, sig)

    var_name = var["var_name"]
    rows: list[TableRow] = []
    for col in item_cols:
        if col not in df.columns:
            continue
        label = item_labels.get(col, col)
        cells: dict[str, TableCell] = {}
        for split_name, split_df in splits.items():
            series = split_df[col].dropna()
            count = int(series.sum())
            base = len(series)
            pct = round(count / base * 100, 1) if base > 0 else 0.0
            cells[split_name] = TableCell(value=count, base=base, pct=pct)
        rows.append(TableRow(label=label, cells=cells))

    base_cells: dict[str, TableCell] = {}
    for split_name, split_df in splits.items():
        base_cells[split_name] = TableCell(value=len(split_df), base=len(split_df))

    return GeneratedTable(
        table_type=TableType.MULTI_SELECT,
        variable_name=var_name,
        question_id=var.get("question_id"),
        question_text=var.get("question_text"),
        banner_columns=list(splits.keys()),
        rows=rows,
        base_row=TableRow(label="Base", cells=base_cells),
    )


def _gen_t2b(
    df: pd.DataFrame, var: dict[str, Any], splits: dict[str, pd.DataFrame], sig: bool,
) -> GeneratedTable:
    """Top-2-Box / Bottom-2-Box for a Likert variable.

    ``var["t2b_codes"]``: list of codes counted as "top box".
    ``var["b2b_codes"]``: list of codes counted as "bottom box".
    Infers from scale range if not provided.
    """
    var_name = var["var_name"]
    if var_name not in df.columns:
        raise TableGenerationError(f"Variable '{var_name}' not found in data.")

    col_data = df[var_name].dropna()
    scale_min = int(col_data.min()) if len(col_data) else 1
    scale_max = int(col_data.max()) if len(col_data) else 5
    t2b_codes = var.get("t2b_codes", [scale_max - 1, scale_max])
    b2b_codes = var.get("b2b_codes", [scale_min, scale_min + 1])

    rows: list[TableRow] = []
    for label, codes in [("Top-2-Box (%)", t2b_codes), ("Bottom-2-Box (%)", b2b_codes)]:
        cells: dict[str, TableCell] = {}
        for split_name, split_df in splits.items():
            series = split_df[var_name].dropna()
            count = int(series.isin(codes).sum())
            base = len(series)
            pct = round(count / base * 100, 1) if base > 0 else 0.0
            cells[split_name] = TableCell(value=count, base=base, pct=pct)
        rows.append(TableRow(label=label, cells=cells))

    base_cells: dict[str, TableCell] = {}
    for split_name, split_df in splits.items():
        n = int(split_df[var_name].notna().sum())
        base_cells[split_name] = TableCell(value=n, base=n)

    return GeneratedTable(
        table_type=TableType.TOP2BOX,
        variable_name=var_name,
        question_id=var.get("question_id"),
        question_text=var.get("question_text"),
        banner_columns=list(splits.keys()),
        rows=rows,
        base_row=TableRow(label="Base", cells=base_cells),
    )


def _gen_mean(
    df: pd.DataFrame, var: dict[str, Any], splits: dict[str, pd.DataFrame], sig: bool,
) -> GeneratedTable:
    """Mean and Std Dev for a numeric / Likert variable."""
    var_name = var["var_name"]
    if var_name not in df.columns:
        raise TableGenerationError(f"Variable '{var_name}' not found in data.")

    rows: list[TableRow] = []
    for stat_label, stat_fn in [("Mean", "mean"), ("Std Dev", "std")]:
        cells: dict[str, TableCell] = {}
        for split_name, split_df in splits.items():
            series = split_df[var_name].dropna()
            base = len(series)
            val = round(float(getattr(series, stat_fn)()), 2) if base > 0 else None
            cells[split_name] = TableCell(value=val, base=base)
        rows.append(TableRow(label=stat_label, cells=cells))

    return GeneratedTable(
        table_type=TableType.MEAN,
        variable_name=var_name,
        question_id=var.get("question_id"),
        question_text=var.get("question_text"),
        banner_columns=list(splits.keys()),
        rows=rows,
    )


def _gen_crosstab(
    df: pd.DataFrame, var: dict[str, Any], splits: dict[str, pd.DataFrame], sig: bool,
) -> GeneratedTable:
    """Cross-tab of a categorical variable against banner splits."""
    var_name = var["var_name"]
    value_labels: dict[int, str] = {int(k): v for k, v in var.get("value_labels", {}).items()}
    if var_name not in df.columns:
        raise TableGenerationError(f"Variable '{var_name}' not found in data.")

    codes = sorted(df[var_name].dropna().unique())
    rows: list[TableRow] = []
    for code in codes:
        label = value_labels.get(int(code), f"Code {int(code)}")
        cells: dict[str, TableCell] = {}
        for split_name, split_df in splits.items():
            col = split_df[var_name].dropna()
            count = int((col == code).sum())
            base = len(col)
            pct = round(count / base * 100, 1) if base > 0 else 0.0
            cells[split_name] = TableCell(value=count, base=base, pct=pct)
        rows.append(TableRow(label=label, code=int(code), cells=cells))

    return GeneratedTable(
        table_type=TableType.CROSSTAB,
        variable_name=var_name,
        question_id=var.get("question_id"),
        question_text=var.get("question_text"),
        banner_columns=list(splits.keys()),
        rows=rows,
    )


_TABLE_GENERATORS = {
    TableType.FREQUENCY: _gen_frequency,
    TableType.MULTI_SELECT: _gen_multi_select,
    TableType.TOP2BOX: _gen_t2b,
    TableType.MEAN: _gen_mean,
    TableType.CROSSTAB: _gen_crosstab,
}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def generate_tables(
    project_id: str,
    mapping_id: str,
    mapping_version: int,
    questionnaire_version: int,
    variables: list[dict[str, Any]],
    df: pd.DataFrame,
    config: TableConfig | None = None,
) -> TableRunResult:
    """Generate tables from a DataFrame and variable mapping.

    Args:
        project_id: Project identifier.
        mapping_id: Mapping version identifier.
        mapping_version: Mapping version number.
        questionnaire_version: Questionnaire version number.
        variables: List of variable descriptors (see module docstring).
        df: Raw survey data with one row per respondent.
        config: Optional table configuration.

    Raises:
        TableGenerationError: On empty data or missing variables.
    """
    if config is None:
        config = TableConfig()
    if df.empty:
        raise TableGenerationError("DataFrame is empty — no data to tabulate.")

    splits = _banner_splits(df, config.banner_variables)
    sig = config.significance.enabled
    tables: list[GeneratedTable] = []

    for var_info in variables:
        for table_type in config.table_types:
            gen = _TABLE_GENERATORS.get(table_type)
            if gen:
                tables.append(gen(df, var_info, splits, sig))

    return TableRunResult(
        project_id=project_id,
        mapping_id=mapping_id,
        mapping_version=mapping_version,
        questionnaire_version=questionnaire_version,
        config=config,
        tables=tables,
    )


# ---------------------------------------------------------------------------
# Run persistence
# ---------------------------------------------------------------------------

def save_run(result: TableRunResult, base_dir: str | Path) -> Path:
    """Serialize a TableRunResult to a run-specific subfolder."""
    run_dir = Path(base_dir) / result.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = run_dir / "manifest.json"
    data = result.model_dump(mode="json")
    manifest.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return run_dir
