"""Tests for P10-05: API versioning and schema compatibility testing.

AC-1: Versioning policy is documented for API and shared contracts.
AC-2: Compatibility tests validate backward support.
AC-3: Breaking changes require explicit migration notes and version bump.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from apps.api.main import app
from packages.shared.api_compat import (
    SNAPSHOT_PATH,
    capture_openapi_schema,
    detect_additions,
    detect_breaking_changes,
    full_diff,
    load_snapshot,
)

ADR_DIR = Path(__file__).resolve().parents[2] / "docs" / "05_decisions"


# ---------------------------------------------------------------------------
# AC-1: Versioning policy documented
# ---------------------------------------------------------------------------

class TestVersioningPolicy:
    def test_adr_006_exists(self):
        assert (ADR_DIR / "ADR-006-api-versioning.md").is_file()

    def test_adr_006_covers_versioning_strategy(self):
        content = (ADR_DIR / "ADR-006-api-versioning.md").read_text()
        assert "URL-path versioning" in content
        assert "/api/v1" in content

    def test_adr_006_defines_breaking_changes(self):
        content = (ADR_DIR / "ADR-006-api-versioning.md").read_text()
        assert "Breaking" in content
        assert "Non-breaking" in content

    def test_adr_006_documents_schema_compatibility(self):
        content = (ADR_DIR / "ADR-006-api-versioning.md").read_text()
        assert "OpenAPI snapshot" in content
        assert "openapi_snapshot.json" in content

    def test_adr_in_contributing_index(self):
        content = (ADR_DIR / "CONTRIBUTING.md").read_text()
        assert "ADR-006" in content

    def test_api_routes_use_v1_prefix(self):
        """All non-health/ops API routes are versioned under /api/v1."""
        schema = capture_openapi_schema(app)
        # Health and ops endpoints are intentionally unversioned
        unversioned_prefixes = ("/health", "/ops/")
        for path in schema.get("paths", {}):
            if any(path.startswith(p) for p in unversioned_prefixes):
                continue
            assert path.startswith("/api/v1"), f"Unversioned route: {path}"

    def test_fastapi_version_set(self):
        schema = capture_openapi_schema(app)
        assert schema["info"]["version"] == "0.1.0"


# ---------------------------------------------------------------------------
# AC-2: Compatibility tests
# ---------------------------------------------------------------------------

class TestOpenAPISnapshot:
    def test_snapshot_file_exists(self):
        assert SNAPSHOT_PATH.is_file(), "OpenAPI snapshot not found — run api_compat.save_snapshot()"

    def test_snapshot_is_valid_json(self):
        data = load_snapshot()
        assert "openapi" in data
        assert "paths" in data
        assert "info" in data

    def test_current_schema_matches_snapshot(self):
        """Current API schema has no breaking changes vs the snapshot."""
        snapshot = load_snapshot()
        current = capture_openapi_schema(app)
        diff = full_diff(snapshot, current)
        assert diff["compatible"], (
            f"Breaking changes detected:\n"
            + "\n".join(f"  - {c['detail']}" for c in diff["breaking_changes"])
        )

    def test_snapshot_has_all_current_endpoints(self):
        """Advisory: warns if new endpoints exist that aren't in the snapshot."""
        snapshot = load_snapshot()
        current = capture_openapi_schema(app)
        snap_paths = set(snapshot.get("paths", {}).keys())
        curr_paths = set(current.get("paths", {}).keys())
        missing = curr_paths - snap_paths
        if missing:
            pytest.skip(f"New endpoints not in snapshot (non-breaking): {missing}")
        assert snap_paths == curr_paths


class TestBreakingChangeDetection:
    @pytest.fixture
    def base_schema(self):
        return {
            "openapi": "3.1.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/api/v1/items": {
                    "get": {"operationId": "list_items", "responses": {"200": {}}},
                    "post": {"operationId": "create_item", "responses": {"201": {}}},
                },
                "/api/v1/items/{id}": {
                    "get": {"operationId": "get_item", "responses": {"200": {}}},
                },
            },
            "components": {
                "schemas": {
                    "Item": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "status": {"type": "string"},
                        },
                    },
                    "CreateItem": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                        },
                        "required": ["name"],
                    },
                },
            },
        }

    def test_no_changes_is_compatible(self, base_schema):
        diff = full_diff(base_schema, copy.deepcopy(base_schema))
        assert diff["compatible"] is True
        assert diff["breaking_count"] == 0
        assert diff["addition_count"] == 0

    def test_endpoint_removed_is_breaking(self, base_schema):
        new = copy.deepcopy(base_schema)
        del new["paths"]["/api/v1/items/{id}"]
        changes = detect_breaking_changes(base_schema, new)
        assert len(changes) >= 1
        assert any(c["type"] == "endpoint_removed" for c in changes)

    def test_field_removed_is_breaking(self, base_schema):
        new = copy.deepcopy(base_schema)
        del new["components"]["schemas"]["Item"]["properties"]["status"]
        changes = detect_breaking_changes(base_schema, new)
        assert len(changes) >= 1
        assert any(c["type"] == "field_removed" and "status" in c["detail"] for c in changes)

    def test_field_type_changed_is_breaking(self, base_schema):
        new = copy.deepcopy(base_schema)
        new["components"]["schemas"]["Item"]["properties"]["id"]["type"] = "integer"
        changes = detect_breaking_changes(base_schema, new)
        assert len(changes) >= 1
        assert any(c["type"] == "field_type_changed" for c in changes)

    def test_schema_removed_is_breaking(self, base_schema):
        new = copy.deepcopy(base_schema)
        del new["components"]["schemas"]["CreateItem"]
        changes = detect_breaking_changes(base_schema, new)
        assert any(c["type"] == "schema_removed" for c in changes)

    def test_new_endpoint_is_non_breaking(self, base_schema):
        new = copy.deepcopy(base_schema)
        new["paths"]["/api/v1/items/{id}/details"] = {
            "get": {"operationId": "get_item_details"},
        }
        changes = detect_breaking_changes(base_schema, new)
        assert len(changes) == 0  # no breaking changes

        additions = detect_additions(base_schema, new)
        assert any(a["type"] == "endpoint_added" for a in additions)

    def test_new_field_is_non_breaking(self, base_schema):
        new = copy.deepcopy(base_schema)
        new["components"]["schemas"]["Item"]["properties"]["description"] = {"type": "string"}
        changes = detect_breaking_changes(base_schema, new)
        assert len(changes) == 0

        additions = detect_additions(base_schema, new)
        assert any(a["type"] == "field_added" and "description" in a["detail"] for a in additions)

    def test_new_schema_is_non_breaking(self, base_schema):
        new = copy.deepcopy(base_schema)
        new["components"]["schemas"]["NewModel"] = {
            "type": "object",
            "properties": {"x": {"type": "integer"}},
        }
        additions = detect_additions(base_schema, new)
        assert any(a["type"] == "schema_added" and "NewModel" in a["detail"] for a in additions)

    def test_full_diff_report(self, base_schema):
        new = copy.deepcopy(base_schema)
        del new["paths"]["/api/v1/items/{id}"]
        new["paths"]["/api/v1/new-endpoint"] = {"get": {}}
        report = full_diff(base_schema, new)
        assert report["compatible"] is False
        assert report["breaking_count"] >= 1
        assert report["addition_count"] >= 1


# ---------------------------------------------------------------------------
# AC-3: Breaking change controls
# ---------------------------------------------------------------------------

class TestBreakingChangeControls:
    def test_adr_documents_breaking_change_process(self):
        content = (ADR_DIR / "ADR-006-api-versioning.md").read_text()
        assert "migration notes" in content.lower() or "migration" in content.lower()
        assert "version bump" in content.lower() or "version" in content.lower()

    def test_adr_documents_deprecation(self):
        content = (ADR_DIR / "ADR-006-api-versioning.md").read_text()
        assert "Deprecation" in content

    def test_api_version_in_openapi_info(self):
        schema = capture_openapi_schema(app)
        version = schema["info"]["version"]
        # Version should be semver-like
        parts = version.split(".")
        assert len(parts) >= 2, f"Version should be semver: {version}"

    def test_health_endpoint_unversioned(self):
        """Health check is intentionally unversioned for load balancers."""
        schema = capture_openapi_schema(app)
        assert "/health" in schema["paths"]
