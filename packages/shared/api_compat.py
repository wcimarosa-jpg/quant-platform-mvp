"""API schema compatibility utilities.

Provides tools for capturing, comparing, and validating OpenAPI schemas
to prevent accidental breaking changes. Used by CI and regression tests.

Breaking change detection:
- Removed endpoints
- Removed required request fields
- Removed response fields
- Changed field types
- Changed HTTP methods
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "golden"
SNAPSHOT_PATH = GOLDEN_DIR / "openapi_snapshot.json"


def capture_openapi_schema(app: Any) -> dict[str, Any]:
    """Extract the OpenAPI schema from a FastAPI app."""
    return app.openapi()


def save_snapshot(schema: dict[str, Any], path: str | Path | None = None) -> Path:
    """Save an OpenAPI schema as the golden snapshot."""
    dest = Path(path) if path else SNAPSHOT_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, sort_keys=True)
    logger.info("Saved OpenAPI snapshot to %s", dest)
    return dest


def load_snapshot(path: str | Path | None = None) -> dict[str, Any]:
    """Load the golden OpenAPI snapshot."""
    src = Path(path) if path else SNAPSHOT_PATH
    if not src.is_file():
        raise FileNotFoundError(f"OpenAPI snapshot not found: {src}")
    with open(src, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Schema diff / breaking change detection
# ---------------------------------------------------------------------------

def _extract_endpoints(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Extract {method:path -> operation} from OpenAPI paths."""
    endpoints = {}
    for path, methods in schema.get("paths", {}).items():
        for method, operation in methods.items():
            if method in ("get", "post", "put", "patch", "delete"):
                endpoints[f"{method.upper()} {path}"] = operation
    return endpoints


def detect_breaking_changes(
    old_schema: dict[str, Any],
    new_schema: dict[str, Any],
) -> list[dict[str, str]]:
    """Compare two OpenAPI schemas and return breaking changes.

    Returns a list of dicts with keys: type, severity, detail.
    Severity is always "breaking" for items returned here.
    """
    changes: list[dict[str, str]] = []

    old_endpoints = _extract_endpoints(old_schema)
    new_endpoints = _extract_endpoints(new_schema)

    # Removed endpoints
    for ep in old_endpoints:
        if ep not in new_endpoints:
            changes.append({
                "type": "endpoint_removed",
                "severity": "breaking",
                "detail": f"Endpoint removed: {ep}",
            })

    # Removed response schema fields
    old_components = old_schema.get("components", {})
    new_components = new_schema.get("components", {})

    old_schemas = old_components.get("schemas", {})
    new_schemas = new_components.get("schemas", {})

    for schema_name, old_def in old_schemas.items():
        if schema_name not in new_schemas:
            changes.append({
                "type": "schema_removed",
                "severity": "breaking",
                "detail": f"Schema removed: {schema_name}",
            })
            continue

        new_def = new_schemas[schema_name]
        old_props = set(old_def.get("properties", {}).keys())
        new_props = set(new_def.get("properties", {}).keys())

        removed_props = old_props - new_props
        for prop in removed_props:
            changes.append({
                "type": "field_removed",
                "severity": "breaking",
                "detail": f"Field removed from {schema_name}: {prop}",
            })

        # Type changes on existing fields
        for prop in old_props & new_props:
            old_type = old_def["properties"][prop].get("type")
            new_type = new_def["properties"][prop].get("type")
            if old_type and new_type and old_type != new_type:
                changes.append({
                    "type": "field_type_changed",
                    "severity": "breaking",
                    "detail": f"Field type changed in {schema_name}.{prop}: {old_type} -> {new_type}",
                })

    return changes


def detect_additions(
    old_schema: dict[str, Any],
    new_schema: dict[str, Any],
) -> list[dict[str, str]]:
    """Detect non-breaking additions (new endpoints, new fields)."""
    additions: list[dict[str, str]] = []

    old_endpoints = _extract_endpoints(old_schema)
    new_endpoints = _extract_endpoints(new_schema)

    for ep in new_endpoints:
        if ep not in old_endpoints:
            additions.append({
                "type": "endpoint_added",
                "severity": "non-breaking",
                "detail": f"New endpoint: {ep}",
            })

    old_schemas = old_schema.get("components", {}).get("schemas", {})
    new_schemas = new_schema.get("components", {}).get("schemas", {})

    for schema_name in new_schemas:
        if schema_name not in old_schemas:
            additions.append({
                "type": "schema_added",
                "severity": "non-breaking",
                "detail": f"New schema: {schema_name}",
            })
            continue

        old_props = set(old_schemas[schema_name].get("properties", {}).keys())
        new_props = set(new_schemas[schema_name].get("properties", {}).keys())
        for prop in new_props - old_props:
            additions.append({
                "type": "field_added",
                "severity": "non-breaking",
                "detail": f"New field in {schema_name}: {prop}",
            })

    return additions


def full_diff(
    old_schema: dict[str, Any],
    new_schema: dict[str, Any],
) -> dict[str, Any]:
    """Full compatibility report between two API schemas."""
    breaking = detect_breaking_changes(old_schema, new_schema)
    additions = detect_additions(old_schema, new_schema)
    return {
        "compatible": len(breaking) == 0,
        "breaking_changes": breaking,
        "additions": additions,
        "breaking_count": len(breaking),
        "addition_count": len(additions),
    }
