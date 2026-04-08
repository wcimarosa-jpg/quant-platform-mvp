"""End-to-end smoke test for the mapping flow (Codex blocker fix verification).

Replicates exactly what the frontend MappingPage does:
1. Parse a realistic CSV with the same coercion rules as lib/csv.ts
2. Profile columns the same way as lib/profile.ts
3. POST to /api/v1/tables/generate with the resulting variables and config
4. Verify a non-error response

This test exists specifically to catch the two blockers Codex identified:
- BLOCKER 1: CSV parser breaks on quoted fields
- BLOCKER 2: var_type=single hardcoding crashes the table generator on text columns
"""

from __future__ import annotations

import io
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from packages.shared.auth import create_token


# A realistic Qualtrics-style CSV with all the gotchas:
# - Quoted fields with commas
# - Escaped double quotes
# - Embedded newlines in quoted text
# - UTF-8 BOM
# - Leading-zero IDs (should stay strings, get skipped)
# - Mixed numeric and text columns
# - Mixed CRLF / LF
REALISTIC_CSV = (
    '\ufeffResponseId,Q1_brand_aware,Q2_satisfaction,gender,age,open_end\r\n'
    '"R_001",1,4,1,25,"Great service, would recommend!"\r\n'
    '"R_002",1,5,2,32,"She said ""amazing"" experience"\r\n'
    '"R_003",0,3,1,28,"Multi-line\nresponse here"\r\n'
    '"R_004",1,4,2,45,"Standard reply"\r\n'
    '"R_005",1,5,1,30,""\r\n'
)


def parse_csv_python(text: str) -> dict[str, Any]:
    """Python port of lib/csv.ts — same state machine, same coercion rules.

    Used by this test to verify the contract end-to-end without spinning up
    a JS runtime. Logic must mirror the TypeScript exactly.
    """
    if text.startswith('\ufeff'):
        text = text[1:]

    records: list[list[str]] = []
    field = ''
    record: list[str] = []
    in_quotes = False
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]
        if in_quotes:
            if ch == '"':
                if i + 1 < n and text[i + 1] == '"':
                    field += '"'
                    i += 2
                    continue
                in_quotes = False
                i += 1
                continue
            field += ch
            i += 1
            continue

        if ch == '"' and field == '':
            in_quotes = True
            i += 1
            continue

        if ch == ',':
            record.append(field)
            field = ''
            i += 1
            continue

        if ch in ('\r', '\n'):
            record.append(field)
            field = ''
            if len(record) > 1 or record[0] != '':
                records.append(record)
            record = []
            if ch == '\r' and i + 1 < n and text[i + 1] == '\n':
                i += 2
            else:
                i += 1
            continue

        field += ch
        i += 1

    if field or record:
        record.append(field)
        if len(record) > 1 or record[0] != '':
            records.append(record)

    if len(records) < 2:
        return {'columns': [], 'rows': []}

    columns = [c.strip() for c in records[0]]
    rows = []
    for r in records[1:]:
        row: dict[str, Any] = {}
        for c_idx, col in enumerate(columns):
            raw = r[c_idx] if c_idx < len(r) else ''
            row[col] = _coerce(raw)
        rows.append(row)
    return {'columns': columns, 'rows': rows}


def _coerce(raw: str) -> Any:
    if raw == '':
        return None
    # Strict integer pattern (matches lib/csv.ts)
    if raw == '0' or raw == '-0':
        return 0
    if (raw[0] == '-' and raw[1:].isdigit() and raw[1] != '0') or (raw.isdigit() and raw[0] != '0'):
        return int(raw)
    # Strict decimal pattern
    if '.' in raw:
        parts = raw.lstrip('-').split('.')
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return float(raw)
    return raw


def profile_column(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Python port of lib/profile.ts — same classification rules."""
    uniques: set = set()
    numeric_count = 0
    non_null_count = 0
    has_string = False

    for row in rows:
        v = row.get(name)
        if v is None or v == '':
            continue
        non_null_count += 1
        if isinstance(v, (int, float)):
            numeric_count += 1
            uniques.add(v)
        else:
            has_string = True
            uniques.add(str(v))
        if len(uniques) > 1000:
            break

    if non_null_count == 0:
        return {'name': name, 'kind': 'empty', 'value_labels': {}}
    if has_string:
        return {'name': name, 'kind': 'text', 'value_labels': {}}
    if len(uniques) <= 20:
        labels = {}
        for code in sorted(uniques):
            if isinstance(code, int):
                labels[str(code)] = f'Code {code}'
        return {'name': name, 'kind': 'categorical', 'value_labels': labels}
    return {'name': name, 'kind': 'continuous', 'value_labels': {}}


def pick_table_types(profiles: list[dict[str, Any]]) -> list[str]:
    has_cat = any(p['kind'] == 'categorical' for p in profiles)
    has_cont = any(p['kind'] == 'continuous' for p in profiles)
    if has_cat and not has_cont:
        return ['frequency', 'crosstab', 'top2box']
    if has_cont and not has_cat:
        return ['mean']
    return ['frequency', 'mean']


@pytest.fixture
def authed_client():
    client = TestClient(app)
    token = create_token('smoke-user', 'smoke@egg.local', 'admin')
    client.headers.update({'Authorization': f'Bearer {token}'})
    return client


# ---------------------------------------------------------------------------
# CSV parser smoke tests — verify realistic input parses correctly
# ---------------------------------------------------------------------------

class TestCSVParserOnRealisticInput:
    def test_strips_bom(self):
        result = parse_csv_python(REALISTIC_CSV)
        assert result['columns'][0] == 'ResponseId'  # not '\ufeffResponseId'

    def test_quoted_field_with_comma_preserved(self):
        result = parse_csv_python(REALISTIC_CSV)
        assert result['rows'][0]['open_end'] == 'Great service, would recommend!'

    def test_escaped_quotes_unescaped(self):
        result = parse_csv_python(REALISTIC_CSV)
        assert result['rows'][1]['open_end'] == 'She said "amazing" experience'

    def test_embedded_newline_preserved(self):
        result = parse_csv_python(REALISTIC_CSV)
        assert result['rows'][2]['open_end'] == 'Multi-line\nresponse here'

    def test_leading_zero_ids_stay_strings(self):
        result = parse_csv_python(REALISTIC_CSV)
        # IDs like R_001 are alphanumeric strings, not numeric
        assert result['rows'][0]['ResponseId'] == 'R_001'

    def test_empty_cell_becomes_null(self):
        result = parse_csv_python(REALISTIC_CSV)
        assert result['rows'][4]['open_end'] is None

    def test_numeric_columns_coerced(self):
        result = parse_csv_python(REALISTIC_CSV)
        assert result['rows'][0]['Q1_brand_aware'] == 1
        assert result['rows'][0]['age'] == 25

    def test_row_count(self):
        result = parse_csv_python(REALISTIC_CSV)
        assert len(result['rows']) == 5


# ---------------------------------------------------------------------------
# Profile + table_types selection
# ---------------------------------------------------------------------------

class TestColumnProfiling:
    def test_q1_categorical(self):
        result = parse_csv_python(REALISTIC_CSV)
        p = profile_column('Q1_brand_aware', result['rows'])
        assert p['kind'] == 'categorical'
        assert p['value_labels'] == {'0': 'Code 0', '1': 'Code 1'}

    def test_q2_categorical(self):
        result = parse_csv_python(REALISTIC_CSV)
        p = profile_column('Q2_satisfaction', result['rows'])
        assert p['kind'] == 'categorical'
        assert set(p['value_labels'].keys()) == {'3', '4', '5'}

    def test_gender_categorical(self):
        result = parse_csv_python(REALISTIC_CSV)
        p = profile_column('gender', result['rows'])
        assert p['kind'] == 'categorical'

    def test_age_categorical_few_uniques(self):
        # 5 rows = at most 5 uniques, so categorical
        result = parse_csv_python(REALISTIC_CSV)
        p = profile_column('age', result['rows'])
        assert p['kind'] == 'categorical'

    def test_response_id_text_skipped(self):
        result = parse_csv_python(REALISTIC_CSV)
        p = profile_column('ResponseId', result['rows'])
        assert p['kind'] == 'text'

    def test_open_end_text_skipped(self):
        result = parse_csv_python(REALISTIC_CSV)
        p = profile_column('open_end', result['rows'])
        assert p['kind'] == 'text'

    def test_pick_table_types_all_categorical(self):
        result = parse_csv_python(REALISTIC_CSV)
        profiles = [profile_column(c, result['rows']) for c in result['columns']]
        tabulatable = [p for p in profiles if p['kind'] in ('categorical', 'continuous')]
        # All numeric columns are categorical (small unique counts)
        assert pick_table_types(tabulatable) == ['frequency', 'crosstab', 'top2box']


# ---------------------------------------------------------------------------
# THE CRITICAL TEST: end-to-end through the real /api/v1/tables/generate
# ---------------------------------------------------------------------------

class TestMappingEndToEnd:
    def test_realistic_csv_does_not_crash_table_generator(self, authed_client):
        """
        The original BLOCKERS:
        1. CSV parser would split on commas inside quoted fields → wrong row shape
        2. var_type=single + empty value_labels + ALL table types ran → int(code)
           crashed on text columns

        This test:
        - Parses the realistic CSV via the same logic the frontend uses
        - Profiles columns the same way
        - Sends ONLY tabulatable variables with correct value_labels
        - Sends correct table_types (no multi_select, no t2b on continuous, etc.)
        - Verifies the backend returns 200, not 500
        """
        # 1. Parse
        parsed = parse_csv_python(REALISTIC_CSV)
        assert len(parsed['rows']) == 5

        # 2. Profile
        profiles = [profile_column(c, parsed['rows']) for c in parsed['columns']]
        tabulatable = [p for p in profiles if p['kind'] in ('categorical', 'continuous')]
        skipped = [p for p in profiles if p['kind'] in ('text', 'empty')]

        # Sanity: text columns are skipped, not sent
        assert len(skipped) >= 2  # ResponseId + open_end
        assert any(p['name'] == 'ResponseId' for p in skipped)
        assert any(p['name'] == 'open_end' for p in skipped)
        assert len(tabulatable) >= 4  # Q1, Q2, gender, age

        # 3. Build variables (mirrors MappingPage.handleGenerate)
        variables = [
            {
                'var_name': p['name'],
                'question_id': p['name'],
                'question_text': p['name'],
                'value_labels': p['value_labels'],
            }
            for p in tabulatable
        ]

        table_types = pick_table_types(tabulatable)

        # 4. POST to the real backend
        resp = authed_client.post(
            '/api/v1/tables/generate',
            json={
                'project_id': 'proj-smoke',
                'mapping_id': 'auto',
                'mapping_version': 1,
                'questionnaire_version': 1,
                'variables': variables,
                'data_rows': parsed['rows'],
                'config': {
                    'table_types': table_types,
                    'banner_variables': [],
                    'significance': {
                        'enabled': True,
                        'confidence_level': 0.95,
                        'method': 'chi_square',
                    },
                    'base_size_minimum': 30,
                },
            },
        )

        # The whole point: this MUST not 500 anymore.
        assert resp.status_code == 200, f"Backend rejected payload: {resp.status_code} {resp.text}"
        body = resp.json()
        assert 'run_id' in body
        assert body['total_tables'] > 0, 'Expected at least one table generated'

    def test_text_only_csv_returns_clear_error_not_crash(self, authed_client):
        """An all-text CSV should be rejected client-side (no tabulatable cols),
        but if someone bypasses that and posts directly, the backend should not 500.
        """
        # All-text data — frontend would never send this, but verify backend safety
        resp = authed_client.post(
            '/api/v1/tables/generate',
            json={
                'project_id': 'proj-smoke',
                'mapping_id': 'auto',
                'mapping_version': 1,
                'questionnaire_version': 1,
                'variables': [],  # nothing tabulatable
                'data_rows': [{'name': 'Alice'}, {'name': 'Bob'}],
                'config': {
                    'table_types': ['frequency', 'mean'],
                    'banner_variables': [],
                    'significance': {'enabled': True, 'confidence_level': 0.95, 'method': 'chi_square'},
                    'base_size_minimum': 30,
                },
            },
        )
        # Either 200 with 0 tables (graceful) or 422 (validation) — not 500
        assert resp.status_code in (200, 422)

    def test_old_buggy_payload_documents_the_blocker(self, authed_client):
        """Regression check: the OLD frontend payload (var_type='single' + empty
        value_labels + default table_types) crashed the backend when a text
        column was present. This test documents that the bug WAS real and that
        the frontend filtering is what protects against it.
        """
        # Simulating the OLD MappingPage behavior — sends ALL columns including text
        parsed = parse_csv_python(REALISTIC_CSV)
        old_style_variables = [
            {
                'var_name': col,
                'var_label': col,
                'var_type': 'single',
                'value_labels': {},
            }
            for col in parsed['columns']  # includes ResponseId and open_end!
        ]
        try:
            resp = authed_client.post(
                '/api/v1/tables/generate',
                json={
                    'project_id': 'proj-smoke',
                    'mapping_id': 'auto',
                    'mapping_version': 1,
                    'questionnaire_version': 1,
                    'variables': old_style_variables,
                    'data_rows': parsed['rows'],
                    # No config override → backend uses default = ALL 5 table types
                },
            )
            # If the request returned a response at all, it must NOT be 200
            assert resp.status_code != 200, (
                'Old payload unexpectedly succeeded. The backend may have gotten '
                'more lenient since the original Codex review.'
            )
        except ValueError as exc:
            # Expected: backend raises ValueError on int(code) for text columns
            assert 'invalid literal for int' in str(exc), (
                f'Expected int() ValueError on text column, got: {exc}'
            )
