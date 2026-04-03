"""Data upload and profiling.

Accepts CSV/XLSX files, computes structural profiles, and persists
file metadata with content hash for provenance tracking.
"""

from __future__ import annotations

import hashlib
import io
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field


MAX_UPLOAD_BYTES = 250 * 1024 * 1024  # 250 MB


class DataFormat(str, Enum):
    CSV = "csv"
    XLSX = "xlsx"


SUPPORTED_EXTENSIONS: dict[str, DataFormat] = {
    ".csv": DataFormat.CSV,
    ".xlsx": DataFormat.XLSX,
}


class DataUploadError(Exception):
    """Raised when data upload or profiling fails."""


class ColumnProfile(BaseModel):
    """Profile for one column."""

    name: str
    dtype: str
    non_null_count: int
    null_count: int
    null_pct: float
    unique_count: int
    sample_values: list[str] = Field(default_factory=list)


class DataProfile(BaseModel):
    """Structural profile of an uploaded data file."""

    profile_id: str = Field(default_factory=lambda: f"prof-{uuid.uuid4().hex[:8]}")
    file_id: str
    filename: str
    file_format: str
    file_hash: str
    size_bytes: int
    row_count: int
    column_count: int
    columns: list[ColumnProfile]
    total_null_count: int
    total_null_pct: float
    profiled_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def missingness_summary(self) -> dict[str, Any]:
        """Return a summary of missing data."""
        cols_with_missing = [c for c in self.columns if c.null_count > 0]
        return {
            "total_cells": self.row_count * self.column_count,
            "total_missing": self.total_null_count,
            "total_missing_pct": round(self.total_null_pct, 2),
            "columns_with_missing": len(cols_with_missing),
            "worst_columns": sorted(
                [{"name": c.name, "null_pct": round(c.null_pct, 2)} for c in cols_with_missing],
                key=lambda x: x["null_pct"],
                reverse=True,
            )[:5],
        }

    def for_ui(self) -> dict[str, Any]:
        """Return profile data structured for the UI."""
        return {
            "profile_id": self.profile_id,
            "file_id": self.file_id,
            "filename": self.filename,
            "file_format": self.file_format,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "size_bytes": self.size_bytes,
            "missingness": self.missingness_summary(),
            "columns": [
                {
                    "name": c.name,
                    "dtype": c.dtype,
                    "null_pct": round(c.null_pct, 2),
                    "unique_count": c.unique_count,
                    "sample_values": c.sample_values,
                }
                for c in self.columns
            ],
        }


class FileMetadata(BaseModel):
    """Persisted file metadata with content hash."""

    file_id: str = Field(default_factory=lambda: f"file-{uuid.uuid4().hex[:8]}")
    filename: str
    file_format: str
    file_hash: str
    size_bytes: int
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    profile_id: str | None = None


# ---------------------------------------------------------------------------
# Format detection and reading
# ---------------------------------------------------------------------------

def detect_format(filename: str) -> DataFormat:
    ext = Path(filename).suffix.lower()
    fmt = SUPPORTED_EXTENSIONS.get(ext)
    if not fmt:
        raise DataUploadError(
            f"Unsupported file format: {ext!r}. Supported: {', '.join(SUPPORTED_EXTENSIONS.keys())}"
        )
    return fmt


def compute_file_hash(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()[:16]}"


def read_dataframe(content: bytes, fmt: DataFormat) -> pd.DataFrame:
    """Read file bytes into a pandas DataFrame."""
    try:
        if fmt == DataFormat.CSV:
            return pd.read_csv(io.BytesIO(content))
        elif fmt == DataFormat.XLSX:
            return pd.read_excel(io.BytesIO(content))
        else:
            raise DataUploadError(f"No reader for format: {fmt.value}")
    except Exception as exc:
        raise DataUploadError(f"Failed to read {fmt.value} file: {exc}") from exc


# ---------------------------------------------------------------------------
# Profiling
# ---------------------------------------------------------------------------

def profile_dataframe(df: pd.DataFrame) -> list[ColumnProfile]:
    """Profile each column in the DataFrame."""
    profiles = []
    for col in df.columns:
        series = df[col]
        null_count = int(series.isna().sum())
        total = len(series)
        non_null = total - null_count
        sample = series.dropna().head(5).astype(str).tolist()
        profiles.append(ColumnProfile(
            name=str(col),
            dtype=str(series.dtype),
            non_null_count=non_null,
            null_count=null_count,
            null_pct=(null_count / total * 100) if total > 0 else 0.0,
            unique_count=int(series.nunique()),
            sample_values=sample,
        ))
    return profiles


def profile_data(content: bytes, filename: str) -> tuple[FileMetadata, DataProfile]:
    """Full profiling pipeline: validate, read, profile.

    Returns (file_metadata, data_profile).
    """
    if len(content) == 0:
        raise DataUploadError("Empty file.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise DataUploadError(f"File too large. Maximum {MAX_UPLOAD_BYTES // (1024*1024)} MB.")

    import os
    safe_filename = os.path.basename(filename)
    fmt = detect_format(safe_filename)
    file_hash = compute_file_hash(content)

    df = read_dataframe(content, fmt)

    if len(df) == 0:
        raise DataUploadError("File contains no data rows.")

    col_profiles = profile_dataframe(df)
    total_cells = len(df) * len(df.columns)
    total_nulls = sum(c.null_count for c in col_profiles)

    file_meta = FileMetadata(
        filename=safe_filename,
        file_format=fmt.value,
        file_hash=file_hash,
        size_bytes=len(content),
    )

    profile = DataProfile(
        file_id=file_meta.file_id,
        filename=safe_filename,
        file_format=fmt.value,
        file_hash=file_hash,
        size_bytes=len(content),
        row_count=len(df),
        column_count=len(df.columns),
        columns=col_profiles,
        total_null_count=total_nulls,
        total_null_pct=(total_nulls / total_cells * 100) if total_cells > 0 else 0.0,
    )

    file_meta.profile_id = profile.profile_id

    return file_meta, profile
