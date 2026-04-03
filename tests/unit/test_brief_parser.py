"""Contract tests for brief ingestion and parsing (P02-01).

AC-1: Brief formats docx/pdf/md accepted.
AC-2: Extracted entities: objectives, audience, category, geography, constraints.
AC-3: Users can manually edit extracted values before saving.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from packages.shared.brief_parser import (
    BriefFields,
    BriefFormat,
    BriefParseError,
    detect_format,
    extract_text,
    extract_text_markdown,
    ingest_brief,
    parse_brief_fields,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test brief content
# ---------------------------------------------------------------------------

SAMPLE_BRIEF_MD = """# Research Brief: KIND Bars Brand Health Study

## Research Objectives:
Understand how consumers perceive KIND Bars compared to key competitors
in the premium snack bar category. Identify growth opportunities among
lapsed users and non-buyers.

## Target Audience:
US adults aged 18-54 who have purchased snack bars in the past 6 months.

## Product Category:
Premium snack bars / health & wellness snacks

## Geographic Scope:
United States, nationally representative

## Constraints:
- LOI: Maximum 15 minutes
- Budget allows for n=1000 completes
- Must include Spanish language option
"""

SAMPLE_BRIEF_INCOMPLETE = """# Quick Study Brief

## Objectives:
Test new product concepts for market viability.
"""


def _make_docx_bytes(text: str) -> bytes:
    """Create a minimal .docx file from text."""
    from docx import Document

    doc = Document()
    for para in text.split("\n\n"):
        if para.strip():
            doc.add_paragraph(para.strip())
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# AC-1: Brief formats docx/pdf/md accepted
# ---------------------------------------------------------------------------

class TestFormatDetection:
    @pytest.mark.parametrize("filename,expected", [
        ("brief.docx", BriefFormat.DOCX),
        ("brief.pdf", BriefFormat.PDF),
        ("brief.md", BriefFormat.MARKDOWN),
        ("brief.markdown", BriefFormat.MARKDOWN),
        ("brief.txt", BriefFormat.MARKDOWN),
        ("BRIEF.DOCX", BriefFormat.DOCX),
    ])
    def test_detect_format(self, filename: str, expected: BriefFormat):
        assert detect_format(filename) == expected

    @pytest.mark.parametrize("filename", ["brief.xlsx", "brief.pptx", "brief.csv", "brief"])
    def test_unsupported_format_raises(self, filename: str):
        with pytest.raises(BriefParseError, match="Unsupported"):
            detect_format(filename)


class TestTextExtraction:
    def test_markdown_extraction(self):
        content = SAMPLE_BRIEF_MD.encode("utf-8")
        text = extract_text(content, BriefFormat.MARKDOWN)
        assert "KIND Bars" in text
        assert "US adults" in text

    def test_docx_extraction(self):
        docx_bytes = _make_docx_bytes(SAMPLE_BRIEF_MD)
        text = extract_text(docx_bytes, BriefFormat.DOCX)
        assert "KIND Bars" in text

    def test_empty_content_raises(self):
        with pytest.raises(BriefParseError, match="empty"):
            extract_text(b"", BriefFormat.MARKDOWN)

    def test_whitespace_only_raises(self):
        with pytest.raises(BriefParseError, match="empty"):
            extract_text(b"   \n\n  ", BriefFormat.MARKDOWN)

    def test_utf8_with_special_chars(self):
        content = "Résumé des objectifs: étudier le marché".encode("utf-8")
        text = extract_text(content, BriefFormat.MARKDOWN)
        assert "Résumé" in text


# ---------------------------------------------------------------------------
# AC-2: Extracted entities
# ---------------------------------------------------------------------------

class TestFieldExtraction:
    def test_full_brief_extracts_all_fields(self):
        fields = parse_brief_fields(SAMPLE_BRIEF_MD, "brief.md", "md")
        assert fields.objectives is not None
        assert "KIND Bars" in fields.objectives
        assert fields.audience is not None
        assert "18-54" in fields.audience
        assert fields.category is not None
        assert "snack" in fields.category.lower()
        assert fields.geography is not None
        assert "United States" in fields.geography
        assert fields.constraints is not None
        assert "15 minutes" in fields.constraints

    def test_incomplete_brief_has_missing_fields(self):
        fields = parse_brief_fields(SAMPLE_BRIEF_INCOMPLETE, "brief.md", "md")
        assert fields.objectives is not None
        missing = fields.missing_fields()
        assert "audience" in missing
        assert "category" in missing
        assert "geography" in missing

    def test_is_complete_true_when_all_present(self):
        fields = parse_brief_fields(SAMPLE_BRIEF_MD, "brief.md", "md")
        assert fields.is_complete()

    def test_is_complete_false_when_missing(self):
        fields = parse_brief_fields(SAMPLE_BRIEF_INCOMPLETE, "brief.md", "md")
        assert not fields.is_complete()

    def test_raw_text_preserved(self):
        fields = parse_brief_fields(SAMPLE_BRIEF_MD, "brief.md", "md")
        assert len(fields.raw_text) > 100
        assert "KIND Bars" in fields.raw_text

    def test_source_metadata_stored(self):
        fields = parse_brief_fields(SAMPLE_BRIEF_MD, "my_brief.md", "md")
        assert fields.source_filename == "my_brief.md"
        assert fields.source_format == "md"

    def test_extracted_at_is_set(self):
        fields = parse_brief_fields(SAMPLE_BRIEF_MD, "brief.md", "md")
        assert fields.extracted_at is not None

    def test_to_brief_context(self):
        fields = parse_brief_fields(SAMPLE_BRIEF_MD, "brief.md", "md")
        ctx = fields.to_brief_context("brief-001")
        assert ctx.brief_id == "brief-001"
        assert "KIND Bars" in ctx.objectives
        assert ctx.audience is not None
        assert ctx.category is not None


class TestAlternativePatterns:
    """Test that various header formats are recognized."""

    def test_goals_header(self):
        text = "Study Goals: Measure brand equity among millennials"
        fields = parse_brief_fields(text)
        assert fields.objectives is not None
        assert "brand equity" in fields.objectives

    def test_purpose_header(self):
        text = "Purpose: Evaluate new packaging concepts"
        fields = parse_brief_fields(text)
        assert fields.objectives is not None

    def test_respondents_header(self):
        text = "Target Respondents: Women 25-44 who shop at Target"
        fields = parse_brief_fields(text)
        assert fields.audience is not None
        assert "Women 25-44" in fields.audience

    def test_industry_header(self):
        text = "Industry: Quick service restaurants"
        fields = parse_brief_fields(text)
        assert fields.category is not None

    def test_market_header(self):
        text = "Markets: US, UK, Germany"
        fields = parse_brief_fields(text)
        assert fields.geography is not None
        assert "US" in fields.geography

    def test_loi_constraint(self):
        text = "LOI: 20 minutes maximum"
        fields = parse_brief_fields(text)
        assert fields.constraints is not None
        assert "20 minutes" in fields.constraints


# ---------------------------------------------------------------------------
# AC-1 + AC-2: Full pipeline
# ---------------------------------------------------------------------------

class TestIngestPipeline:
    def test_ingest_markdown(self):
        fields = ingest_brief(SAMPLE_BRIEF_MD.encode("utf-8"), "brief.md")
        assert fields.is_complete()
        assert fields.source_format == "md"

    def test_ingest_docx(self):
        docx_bytes = _make_docx_bytes(SAMPLE_BRIEF_MD)
        fields = ingest_brief(docx_bytes, "brief.docx")
        assert fields.objectives is not None
        assert fields.source_format == "docx"

    def test_ingest_unsupported_raises(self):
        with pytest.raises(BriefParseError, match="Unsupported"):
            ingest_brief(b"data", "brief.xlsx")


# ---------------------------------------------------------------------------
# AC-3: Users can manually edit extracted values (API tests)
# ---------------------------------------------------------------------------

class TestBriefAPI:
    def _upload_brief(self) -> str:
        """Upload a sample brief and return brief_id."""
        resp = client.post(
            "/api/v1/briefs/upload?project_id=proj-001",
            files={"file": ("test_brief.md", SAMPLE_BRIEF_MD.encode("utf-8"), "text/markdown")},
        )
        assert resp.status_code == 200
        return resp.json()["brief_id"]

    def test_upload_returns_extracted_fields(self):
        resp = client.post(
            "/api/v1/briefs/upload?project_id=proj-001",
            files={"file": ("test_brief.md", SAMPLE_BRIEF_MD.encode("utf-8"), "text/markdown")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["project_id"] == "proj-001"
        assert body["extracted_fields"]["objectives"] is not None
        assert body["extracted_fields"]["audience"] is not None
        assert body["is_complete"] is True

    def test_upload_docx(self):
        docx_bytes = _make_docx_bytes(SAMPLE_BRIEF_MD)
        resp = client.post(
            "/api/v1/briefs/upload?project_id=proj-001",
            files={"file": ("brief.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert resp.status_code == 200
        assert resp.json()["source_format"] == "docx"

    def test_upload_empty_file_returns_400(self):
        resp = client.post(
            "/api/v1/briefs/upload?project_id=proj-001",
            files={"file": ("empty.md", b"", "text/markdown")},
        )
        assert resp.status_code == 400

    def test_upload_oversized_file_returns_413(self):
        big_content = b"x" * (11 * 1024 * 1024)  # 11 MB
        resp = client.post(
            "/api/v1/briefs/upload?project_id=proj-001",
            files={"file": ("big.md", big_content, "text/markdown")},
        )
        assert resp.status_code == 413

    def test_upload_unsupported_format_returns_422(self):
        resp = client.post(
            "/api/v1/briefs/upload?project_id=proj-001",
            files={"file": ("data.xlsx", b"fake", "application/octet-stream")},
        )
        assert resp.status_code == 422

    def test_get_brief(self):
        brief_id = self._upload_brief()
        resp = client.get(f"/api/v1/briefs/{brief_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["brief_id"] == brief_id
        assert body["objectives"] is not None

    def test_get_nonexistent_brief_returns_404(self):
        resp = client.get("/api/v1/briefs/nonexistent")
        assert resp.status_code == 404

    def test_edit_brief_fields(self):
        brief_id = self._upload_brief()
        resp = client.patch(
            f"/api/v1/briefs/{brief_id}",
            json={"audience": "Adults 25-44 in urban markets", "geography": "US and Canada"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["audience"] == "Adults 25-44 in urban markets"
        assert body["geography"] == "US and Canada"

    def test_edit_preserves_unedited_fields(self):
        brief_id = self._upload_brief()
        original = client.get(f"/api/v1/briefs/{brief_id}").json()
        client.patch(f"/api/v1/briefs/{brief_id}", json={"audience": "New audience"})
        updated = client.get(f"/api/v1/briefs/{brief_id}").json()
        assert updated["audience"] == "New audience"
        assert updated["objectives"] == original["objectives"]
        assert updated["category"] == original["category"]

    def test_edit_nonexistent_brief_returns_404(self):
        resp = client.patch("/api/v1/briefs/nonexistent", json={"audience": "x"})
        assert resp.status_code == 404

    def test_filename_sanitized(self):
        """Path traversal in filename should be stripped."""
        resp = client.post(
            "/api/v1/briefs/upload?project_id=proj-001",
            files={"file": ("../../etc/passwd.md", SAMPLE_BRIEF_MD.encode("utf-8"), "text/markdown")},
        )
        assert resp.status_code == 200
        assert resp.json()["source_filename"] == "passwd.md"

    def test_get_brief_shows_truncation_flag(self):
        brief_id = self._upload_brief()
        resp = client.get(f"/api/v1/briefs/{brief_id}")
        body = resp.json()
        assert "raw_text_truncated" in body

    def test_edit_fills_missing_field(self):
        """Upload incomplete brief, then manually fill missing fields."""
        resp = client.post(
            "/api/v1/briefs/upload?project_id=proj-001",
            files={"file": ("incomplete.md", SAMPLE_BRIEF_INCOMPLETE.encode("utf-8"), "text/markdown")},
        )
        brief_id = resp.json()["brief_id"]
        assert resp.json()["is_complete"] is False

        # Fill missing fields
        client.patch(f"/api/v1/briefs/{brief_id}", json={
            "audience": "US adults 18-34",
            "category": "Plant-based snacks",
            "geography": "United States",
        })
        updated = client.get(f"/api/v1/briefs/{brief_id}").json()
        assert updated["is_complete"] is True
        assert updated["missing_fields"] == []
