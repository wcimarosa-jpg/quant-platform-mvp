"""Research brief ingestion and parsing pipeline.

Accepts .docx, .pdf, and .md files. Extracts raw text and parses
into structured BriefFields for user review and editing.
"""

from __future__ import annotations

import io
import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .assistant_context import BriefContext


class BriefFormat(str, Enum):
    DOCX = "docx"
    PDF = "pdf"
    MARKDOWN = "md"


SUPPORTED_EXTENSIONS: dict[str, BriefFormat] = {
    ".docx": BriefFormat.DOCX,
    ".pdf": BriefFormat.PDF,
    ".md": BriefFormat.MARKDOWN,
    ".markdown": BriefFormat.MARKDOWN,
    ".txt": BriefFormat.MARKDOWN,  # treat plain text as markdown
}


class BriefParseError(Exception):
    """Raised when brief parsing fails."""


# ---------------------------------------------------------------------------
# Raw text extraction — one function per format
# ---------------------------------------------------------------------------

def extract_text_docx(content: bytes) -> str:
    """Extract text from a .docx file."""
    from docx import Document

    doc = Document(io.BytesIO(content))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def extract_text_pdf(content: bytes) -> str:
    """Extract text from a .pdf file."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(p.strip() for p in pages if p.strip())


def extract_text_markdown(content: bytes) -> str:
    """Extract text from a .md or .txt file."""
    return content.decode("utf-8", errors="replace").strip()


_EXTRACTORS = {
    BriefFormat.DOCX: extract_text_docx,
    BriefFormat.PDF: extract_text_pdf,
    BriefFormat.MARKDOWN: extract_text_markdown,
}


def extract_text(content: bytes, fmt: BriefFormat) -> str:
    """Extract plain text from a brief file."""
    extractor = _EXTRACTORS.get(fmt)
    if not extractor:
        raise BriefParseError(f"No extractor for format: {fmt.value}")
    try:
        text = extractor(content)
    except Exception as exc:
        raise BriefParseError(f"Failed to extract text from {fmt.value}: {exc}") from exc
    if not text.strip():
        raise BriefParseError("Extracted text is empty.")
    return text


def detect_format(filename: str) -> BriefFormat:
    """Detect brief format from filename extension."""
    ext = Path(filename).suffix.lower()
    fmt = SUPPORTED_EXTENSIONS.get(ext)
    if not fmt:
        raise BriefParseError(
            f"Unsupported file extension: {ext!r}. "
            f"Supported: {', '.join(SUPPORTED_EXTENSIONS.keys())}"
        )
    return fmt


# ---------------------------------------------------------------------------
# Structured field extraction — regex-based heuristic extraction
# ---------------------------------------------------------------------------

class BriefFields(BaseModel):
    """Structured fields extracted from a research brief.

    All fields are optional — users review and edit before saving.
    """

    objectives: str | None = None
    audience: str | None = None
    category: str | None = None
    geography: str | None = None
    constraints: str | None = None
    raw_text: str = ""
    source_filename: str = ""
    source_format: str = ""
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def missing_fields(self) -> list[str]:
        """Return names of fields that are still None."""
        required = ["objectives", "audience", "category", "geography"]
        return [f for f in required if getattr(self, f) is None]

    def is_complete(self) -> bool:
        return len(self.missing_fields()) == 0

    def to_brief_context(self, brief_id: str) -> BriefContext:
        """Convert to a BriefContext for the assistant context contract."""
        return BriefContext(
            brief_id=brief_id,
            objectives=self.objectives or "",
            audience=self.audience,
            category=self.category,
            geography=self.geography,
            constraints=self.constraints,
            uploaded_at=self.extracted_at,
        )


# Section header patterns for heuristic extraction
_SECTION_PATTERNS: dict[str, list[re.Pattern]] = {
    "objectives": [
        re.compile(r"(?:research\s+)?objectives?\s*[:\-–]\s*(.*)", re.IGNORECASE | re.DOTALL),
        re.compile(r"(?:study\s+)?goals?\s*[:\-–]\s*(.*)", re.IGNORECASE | re.DOTALL),
        re.compile(r"purpose\s*[:\-–]\s*(.*)", re.IGNORECASE | re.DOTALL),
    ],
    "audience": [
        re.compile(r"(?:target\s+)?audience\s*[:\-–]\s*(.*)", re.IGNORECASE | re.DOTALL),
        re.compile(r"(?:target\s+)?(?:respondents?|participants?|sample)\s*[:\-–]\s*(.*)", re.IGNORECASE | re.DOTALL),
        re.compile(r"who\s+(?:are\s+)?we\s+(?:talking|speaking)\s+to\s*[:\-–]?\s*(.*)", re.IGNORECASE | re.DOTALL),
    ],
    "category": [
        re.compile(r"(?:product\s+)?category\s*[:\-–]\s*(.*)", re.IGNORECASE | re.DOTALL),
        re.compile(r"(?:industry|sector|vertical)\s*[:\-–]\s*(.*)", re.IGNORECASE | re.DOTALL),
    ],
    "geography": [
        re.compile(r"(?:geographic?\s+)?(?:scope|market|region|geography)\s*[:\-–]\s*(.*)", re.IGNORECASE | re.DOTALL),
        re.compile(r"(?:countries?|markets?)\s*[:\-–]\s*(.*)", re.IGNORECASE | re.DOTALL),
    ],
    "constraints": [
        re.compile(r"constraints?\s*[:\-–]\s*(.*)", re.IGNORECASE | re.DOTALL),
        re.compile(r"(?:budget|timeline|limitations?|requirements?)\s*[:\-–]\s*(.*)", re.IGNORECASE | re.DOTALL),
        re.compile(r"(?:LOI|length\s+of\s+interview)\s*[:\-–]\s*(.*)", re.IGNORECASE | re.DOTALL),
    ],
}


def _extract_section(text: str, patterns: list[re.Pattern]) -> str | None:
    """Try each pattern against the text. Return first match, trimmed to first paragraph."""
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            value = match.group(1).strip()
            # Trim to first paragraph break or next section header
            para_break = re.search(r"\n\s*\n|\n[A-Z][a-z]+\s*[:\-–]", value)
            if para_break:
                value = value[:para_break.start()].strip()
            if value:
                return value
    return None


def parse_brief_fields(text: str, filename: str = "", fmt: str = "") -> BriefFields:
    """Extract structured fields from raw brief text using heuristic patterns."""
    fields: dict[str, str | None] = {}
    for field_name, patterns in _SECTION_PATTERNS.items():
        fields[field_name] = _extract_section(text, patterns)

    return BriefFields(
        objectives=fields.get("objectives"),
        audience=fields.get("audience"),
        category=fields.get("category"),
        geography=fields.get("geography"),
        constraints=fields.get("constraints"),
        raw_text=text,
        source_filename=filename,
        source_format=fmt,
    )


# ---------------------------------------------------------------------------
# Full pipeline — file bytes in, structured fields out
# ---------------------------------------------------------------------------

def ingest_brief(content: bytes, filename: str) -> BriefFields:
    """Full ingestion pipeline: detect format, extract text, parse fields."""
    fmt = detect_format(filename)
    text = extract_text(content, fmt)
    return parse_brief_fields(text, filename=filename, fmt=fmt.value)
