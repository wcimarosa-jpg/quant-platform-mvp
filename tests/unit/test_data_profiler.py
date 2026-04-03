"""Contract tests for data upload and profiling (P05-01).

AC-1: Files up to 250MB upload successfully.
AC-2: Profile includes row count, columns, missingness summary.
AC-3: File metadata and hash are persisted.
"""

from __future__ import annotations

import io

import pandas as pd
import pytest

from packages.shared.data_profiler import (
    MAX_UPLOAD_BYTES,
    ColumnProfile,
    DataFormat,
    DataProfile,
    DataUploadError,
    FileMetadata,
    compute_file_hash,
    detect_format,
    profile_data,
    profile_dataframe,
    read_dataframe,
)


def _csv_bytes(rows: int = 100, cols: int = 5, missing_pct: float = 0.0) -> bytes:
    """Generate CSV bytes with optional missing values."""
    import numpy as np
    data = {}
    for i in range(cols):
        col = np.random.randint(1, 100, size=rows).astype(float)
        if missing_pct > 0:
            mask = np.random.random(rows) < missing_pct
            col[mask] = np.nan
        data[f"col_{i+1}"] = col
    df = pd.DataFrame(data)
    return df.to_csv(index=False).encode("utf-8")


def _xlsx_bytes(rows: int = 50) -> bytes:
    df = pd.DataFrame({"Q1": range(rows), "Q2": [f"val_{i}" for i in range(rows)]})
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# AC-1: Files up to 250MB upload successfully
# ---------------------------------------------------------------------------

class TestFileUpload:
    def test_csv_upload(self):
        content = _csv_bytes(100, 5)
        meta, profile = profile_data(content, "survey_data.csv")
        assert profile.row_count == 100
        assert profile.column_count == 5

    def test_xlsx_upload(self):
        content = _xlsx_bytes(50)
        meta, profile = profile_data(content, "data.xlsx")
        assert profile.row_count == 50
        assert profile.column_count == 2
        assert profile.file_format == "xlsx"

    def test_empty_file_rejected(self):
        with pytest.raises(DataUploadError, match="Empty"):
            profile_data(b"", "empty.csv")

    def test_unsupported_format_rejected(self):
        with pytest.raises(DataUploadError, match="Unsupported"):
            profile_data(b"data", "file.json")

    def test_no_data_rows_rejected(self):
        content = b"col1,col2\n"  # header only
        with pytest.raises(DataUploadError, match="no data"):
            profile_data(content, "empty_data.csv")

    def test_size_limit_enforced(self):
        big = b"x" * (MAX_UPLOAD_BYTES + 1)
        with pytest.raises(DataUploadError, match="too large"):
            profile_data(big, "huge.csv")

    def test_format_detection(self):
        assert detect_format("data.csv") == DataFormat.CSV
        assert detect_format("DATA.XLSX") == DataFormat.XLSX
        assert detect_format("report.CSV") == DataFormat.CSV

    def test_filename_sanitized(self):
        content = _csv_bytes(10, 2)
        meta, profile = profile_data(content, "../../etc/passwd.csv")
        assert meta.filename == "passwd.csv"
        assert profile.filename == "passwd.csv"


# ---------------------------------------------------------------------------
# AC-2: Profile includes row count, columns, missingness summary
# ---------------------------------------------------------------------------

class TestProfileContent:
    def test_row_and_column_counts(self):
        content = _csv_bytes(200, 8)
        _, profile = profile_data(content, "test.csv")
        assert profile.row_count == 200
        assert profile.column_count == 8

    def test_column_profiles_present(self):
        content = _csv_bytes(50, 3)
        _, profile = profile_data(content, "test.csv")
        assert len(profile.columns) == 3
        for col in profile.columns:
            assert isinstance(col, ColumnProfile)
            assert col.name
            assert col.dtype

    def test_column_profile_has_required_fields(self):
        content = _csv_bytes(50, 3)
        _, profile = profile_data(content, "test.csv")
        for col in profile.columns:
            assert col.non_null_count >= 0
            assert col.null_count >= 0
            assert 0.0 <= col.null_pct <= 100.0
            assert col.unique_count >= 0

    def test_missingness_with_clean_data(self):
        content = _csv_bytes(100, 5, missing_pct=0.0)
        _, profile = profile_data(content, "clean.csv")
        summary = profile.missingness_summary()
        assert summary["total_missing"] == 0
        assert summary["columns_with_missing"] == 0

    def test_missingness_with_dirty_data(self):
        content = _csv_bytes(100, 5, missing_pct=0.2)
        _, profile = profile_data(content, "dirty.csv")
        summary = profile.missingness_summary()
        assert summary["total_missing"] > 0
        assert summary["columns_with_missing"] > 0
        assert len(summary["worst_columns"]) > 0
        for wc in summary["worst_columns"]:
            assert "name" in wc
            assert "null_pct" in wc

    def test_sample_values_populated(self):
        content = _csv_bytes(50, 3)
        _, profile = profile_data(content, "test.csv")
        for col in profile.columns:
            assert len(col.sample_values) > 0
            assert len(col.sample_values) <= 5

    def test_for_ui_output(self):
        content = _csv_bytes(50, 3)
        _, profile = profile_data(content, "test.csv")
        ui = profile.for_ui()
        assert ui["row_count"] == 50
        assert ui["column_count"] == 3
        assert "missingness" in ui
        assert len(ui["columns"]) == 3
        for col in ui["columns"]:
            assert "name" in col
            assert "dtype" in col
            assert "null_pct" in col
            assert "sample_values" in col


# ---------------------------------------------------------------------------
# AC-3: File metadata and hash are persisted
# ---------------------------------------------------------------------------

class TestMetadataAndHash:
    def test_file_metadata_returned(self):
        content = _csv_bytes(50, 3)
        meta, _ = profile_data(content, "test.csv")
        assert isinstance(meta, FileMetadata)
        assert meta.file_id
        assert meta.filename == "test.csv"
        assert meta.file_format == "csv"

    def test_file_hash_computed(self):
        content = _csv_bytes(50, 3)
        meta, profile = profile_data(content, "test.csv")
        assert meta.file_hash.startswith("sha256:")
        assert len(meta.file_hash) > 10
        assert profile.file_hash == meta.file_hash

    def test_hash_is_deterministic(self):
        content = _csv_bytes(50, 3)
        h1 = compute_file_hash(content)
        h2 = compute_file_hash(content)
        assert h1 == h2

    def test_hash_changes_with_content(self):
        c1 = b"col1,col2\n1,2\n"
        c2 = b"col1,col2\n3,4\n"
        assert compute_file_hash(c1) != compute_file_hash(c2)

    def test_size_bytes_stored(self):
        content = _csv_bytes(50, 3)
        meta, profile = profile_data(content, "test.csv")
        assert meta.size_bytes == len(content)
        assert profile.size_bytes == len(content)

    def test_uploaded_at_set(self):
        content = _csv_bytes(10, 2)
        meta, _ = profile_data(content, "test.csv")
        assert meta.uploaded_at is not None

    def test_profile_id_linked(self):
        content = _csv_bytes(10, 2)
        meta, profile = profile_data(content, "test.csv")
        assert meta.profile_id == profile.profile_id

    def test_profiled_at_set(self):
        content = _csv_bytes(10, 2)
        _, profile = profile_data(content, "test.csv")
        assert profile.profiled_at is not None
