"""Formal plugin contract for analysis methodologies.

Defines the Protocol, metadata, and registration helpers that every
analysis plugin must satisfy. This is the single source of truth for
"what does it mean to be an analysis plugin?"

Usage for plugin authors:

    from packages.survey_analysis.plugin_contract import (
        AnalysisPlugin,
        PluginMetadata,
        register_plugin,
    )

    @register_plugin(
        analysis_type="my_analysis",
        version="1.0.0",
        description="My custom analysis",
        required_kwargs=["df", "target_col"],
        result_schema=MyResultSummary,
    )
    def run_my_analysis(run: AnalysisRun, **kwargs) -> dict[str, Any]:
        ...
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Plugin protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class AnalysisPlugin(Protocol):
    """Protocol that all analysis functions must satisfy.

    An analysis function receives an AnalysisRun and keyword arguments,
    and returns a dict that validates against the registered result schema.

    Error contract:
    - Raise AnalysisError for expected, actionable failures
      (bad input, insufficient data, convergence failure).
    - Let unexpected exceptions propagate — the orchestrator catches them.
    """

    def __call__(self, run: Any, **kwargs: Any) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Plugin metadata
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PluginMetadata:
    """Metadata for a registered analysis plugin."""

    analysis_type: str
    version: str
    description: str
    required_kwargs: list[str] = field(default_factory=list)
    optional_kwargs: list[str] = field(default_factory=list)
    result_schema: type[BaseModel] | None = None
    is_composite: bool = False
    tags: list[str] = field(default_factory=list)

    def validate_kwargs(self, kwargs: dict[str, Any]) -> list[str]:
        """Return list of missing required kwargs."""
        return [k for k in self.required_kwargs if k not in kwargs]


# ---------------------------------------------------------------------------
# Plugin registry
# ---------------------------------------------------------------------------

_PLUGIN_METADATA: dict[str, PluginMetadata] = {}


def register_plugin(
    analysis_type: str,
    *,
    version: str = "1.0.0",
    description: str = "",
    required_kwargs: list[str] | None = None,
    optional_kwargs: list[str] | None = None,
    result_schema: type[BaseModel] | None = None,
    tags: list[str] | None = None,
) -> Callable:
    """Decorator that registers an analysis function with full metadata.

    This wraps the existing @register_analysis decorator with rich metadata,
    making plugins discoverable, self-documenting, and validatable.

    Example:
        @register_plugin(
            analysis_type="drivers",
            version="1.0.0",
            description="Ridge regression, Pearson correlations, weighted-effects",
            required_kwargs=["df", "iv_cols", "dv_cols"],
            result_schema=DriversResultSummary,
        )
        def run_drivers(run, **kwargs):
            ...
    """
    def decorator(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
        meta = PluginMetadata(
            analysis_type=analysis_type,
            version=version,
            description=description,
            required_kwargs=required_kwargs or [],
            optional_kwargs=optional_kwargs or [],
            result_schema=result_schema,
            tags=tags or [],
        )
        _PLUGIN_METADATA[analysis_type] = meta

        # Also register in the orchestrator's function registry
        from packages.survey_analysis.run_orchestrator import _ANALYSIS_REGISTRY
        _ANALYSIS_REGISTRY[analysis_type] = fn

        # Also register result schema if provided
        if result_schema:
            from packages.survey_analysis.result_schemas import RESULT_SCHEMAS
            RESULT_SCHEMAS[analysis_type] = result_schema

        logger.info("Registered plugin: %s v%s", analysis_type, version)
        return fn

    return decorator


def register_composite_plugin(
    analysis_type: str,
    steps: list[Callable[..., dict[str, Any]]],
    *,
    version: str = "1.0.0",
    description: str = "",
    required_kwargs: list[str] | None = None,
    optional_kwargs: list[str] | None = None,
    result_schema: type[BaseModel] | None = None,
    tags: list[str] | None = None,
) -> None:
    """Register a composite (multi-step) analysis with metadata.

    Steps are chained: each receives (run, previous_results=dict, **kwargs).
    Key-ownership convention: each step MUST namespace its output keys
    to avoid collisions (e.g., varclus_*, kmeans_*).
    """
    meta = PluginMetadata(
        analysis_type=analysis_type,
        version=version,
        description=description,
        required_kwargs=required_kwargs or [],
        optional_kwargs=optional_kwargs or [],
        result_schema=result_schema,
        is_composite=True,
        tags=tags or [],
    )
    _PLUGIN_METADATA[analysis_type] = meta

    from packages.survey_analysis.run_orchestrator import register_composite
    register_composite(analysis_type, steps)

    if result_schema:
        from packages.survey_analysis.result_schemas import RESULT_SCHEMAS
        RESULT_SCHEMAS[analysis_type] = result_schema

    logger.info("Registered composite plugin: %s v%s (%d steps)", analysis_type, version, len(steps))


# ---------------------------------------------------------------------------
# Discovery and introspection
# ---------------------------------------------------------------------------

def get_plugin_metadata(analysis_type: str) -> PluginMetadata | None:
    """Get metadata for a registered plugin."""
    return _PLUGIN_METADATA.get(analysis_type)


def list_plugins() -> list[PluginMetadata]:
    """Return metadata for all registered plugins, sorted by type."""
    return sorted(_PLUGIN_METADATA.values(), key=lambda m: m.analysis_type)


def get_plugin_catalog() -> list[dict[str, Any]]:
    """Return a serializable catalog of all plugins for API/dashboard use."""
    return [
        {
            "analysis_type": m.analysis_type,
            "version": m.version,
            "description": m.description,
            "required_kwargs": m.required_kwargs,
            "optional_kwargs": m.optional_kwargs,
            "has_result_schema": m.result_schema is not None,
            "is_composite": m.is_composite,
            "tags": m.tags,
        }
        for m in list_plugins()
    ]


def validate_plugin_kwargs(analysis_type: str, kwargs: dict[str, Any]) -> list[str]:
    """Validate kwargs against the plugin's required_kwargs.

    Returns list of missing required kwargs (empty = valid).
    """
    meta = _PLUGIN_METADATA.get(analysis_type)
    if not meta:
        raise ValueError(f"No plugin registered for analysis_type: {analysis_type!r}")
    return meta.validate_kwargs(kwargs)
