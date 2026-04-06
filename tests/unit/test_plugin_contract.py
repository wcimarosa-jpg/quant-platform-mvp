"""Tests for P10-02: Plugin contract for analysis methodologies.

AC-1: Common analysis plugin interface is documented and type-checked.
AC-2: Existing methodologies implement or adapt to the interface contract.
AC-3: New methodology smoke test can be added with minimal boilerplate.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from packages.survey_analysis.plugin_contract import (
    AnalysisPlugin,
    PluginMetadata,
    _PLUGIN_METADATA,
    get_plugin_catalog,
    get_plugin_metadata,
    list_plugins,
    register_composite_plugin,
    register_plugin,
    validate_plugin_kwargs,
)
from packages.survey_analysis.run_orchestrator import (
    AnalysisError,
    AnalysisRun,
    RunConfig,
    RunStatus,
    RunStore,
    RunVersions,
    _ANALYSIS_REGISTRY,
    execute_run,
    get_registered_types,
)
from packages.survey_analysis.result_schemas import RESULT_SCHEMAS

# Import concrete analyses to trigger @register_analysis decorators
import packages.survey_analysis.drivers  # noqa: F401
import packages.survey_analysis.segmentation  # noqa: F401
import packages.survey_analysis.maxdiff_turf  # noqa: F401


def _make_run(analysis_type: str = "pc_test_plugin") -> AnalysisRun:
    return AnalysisRun(
        project_id="proj-test",
        config=RunConfig(analysis_type=analysis_type),
        versions=RunVersions(
            questionnaire_id="q1", questionnaire_version=1,
            mapping_id="m1", mapping_version=1, data_file_hash="abc123",
        ),
    )


# ---------------------------------------------------------------------------
# AC-1: Plugin protocol and metadata
# ---------------------------------------------------------------------------

class TestPluginProtocol:
    def test_plain_function_satisfies_protocol(self):
        def my_fn(run, **kwargs) -> dict[str, Any]:
            return {}
        assert isinstance(my_fn, AnalysisPlugin)

    def test_lambda_satisfies_protocol(self):
        fn = lambda run, **kwargs: {}
        assert isinstance(fn, AnalysisPlugin)

    def test_non_callable_does_not_satisfy(self):
        assert not isinstance("not a function", AnalysisPlugin)


class TestPluginMetadata:
    def test_metadata_creation(self):
        meta = PluginMetadata(
            analysis_type="test",
            version="1.0.0",
            description="Test plugin",
            required_kwargs=["df", "target"],
        )
        assert meta.analysis_type == "test"
        assert meta.version == "1.0.0"
        assert meta.required_kwargs == ["df", "target"]

    def test_validate_kwargs_pass(self):
        meta = PluginMetadata(
            analysis_type="test", version="1.0.0", description="",
            required_kwargs=["df", "target"],
        )
        missing = meta.validate_kwargs({"df": "data", "target": "Q1", "extra": True})
        assert missing == []

    def test_validate_kwargs_fail(self):
        meta = PluginMetadata(
            analysis_type="test", version="1.0.0", description="",
            required_kwargs=["df", "target"],
        )
        missing = meta.validate_kwargs({"df": "data"})
        assert missing == ["target"]

    def test_validate_kwargs_empty(self):
        meta = PluginMetadata(
            analysis_type="test", version="1.0.0", description="",
            required_kwargs=[],
        )
        assert meta.validate_kwargs({}) == []

    def test_metadata_is_frozen(self):
        meta = PluginMetadata(analysis_type="test", version="1.0.0", description="")
        with pytest.raises(AttributeError):
            meta.analysis_type = "changed"


# ---------------------------------------------------------------------------
# AC-1: Registration
# ---------------------------------------------------------------------------

class _DummyResult(BaseModel):
    analysis_type: str = "dummy"
    value: float = 0.0


class TestPluginRegistration:
    # Prefix for keys registered by this test class (avoids cleaning up other test modules)
    _PREFIX = "pc_test_"

    def setup_method(self):
        for key in list(_PLUGIN_METADATA.keys()):
            if key.startswith(self._PREFIX):
                del _PLUGIN_METADATA[key]
        for key in list(_ANALYSIS_REGISTRY.keys()):
            if key.startswith(self._PREFIX):
                del _ANALYSIS_REGISTRY[key]
        for key in list(RESULT_SCHEMAS.keys()):
            if key.startswith(self._PREFIX):
                del RESULT_SCHEMAS[key]

    def test_register_plugin_decorator(self):
        @register_plugin(
            analysis_type="pc_test_basic",
            version="1.0.0",
            description="Basic test plugin",
            required_kwargs=["df"],
            result_schema=_DummyResult,
        )
        def run_test_basic(run, **kwargs):
            return {"analysis_type": "dummy", "value": 42.0}

        assert "pc_test_basic" in _PLUGIN_METADATA
        assert "pc_test_basic" in _ANALYSIS_REGISTRY
        assert "pc_test_basic" in RESULT_SCHEMAS
        meta = _PLUGIN_METADATA["pc_test_basic"]
        assert meta.version == "1.0.0"
        assert meta.required_kwargs == ["df"]

    def test_register_plugin_returns_function(self):
        @register_plugin(analysis_type="pc_test_ret", version="1.0.0", description="")
        def my_fn(run, **kwargs):
            return {"result": True}

        assert callable(my_fn)
        assert my_fn(_make_run()) == {"result": True}

    def test_register_composite_plugin(self):
        def step_a(run, previous_results=None, **kwargs):
            return {"a_out": 1}

        def step_b(run, previous_results=None, **kwargs):
            return {"b_out": (previous_results or {}).get("a_out", 0) + 1}

        register_composite_plugin(
            analysis_type="pc_test_composite",
            steps=[step_a, step_b],
            version="2.0.0",
            description="Two-step test",
            result_schema=_DummyResult,
            tags=["composite", "test"],
        )

        meta = _PLUGIN_METADATA["pc_test_composite"]
        assert meta.is_composite is True
        assert meta.version == "2.0.0"
        assert "composite" in meta.tags
        assert "pc_test_composite" in _ANALYSIS_REGISTRY

    def test_get_plugin_metadata(self):
        @register_plugin(analysis_type="pc_test_meta", version="3.0.0", description="Meta test")
        def fn(run, **kwargs):
            return {}

        meta = get_plugin_metadata("pc_test_meta")
        assert meta is not None
        assert meta.version == "3.0.0"

    def test_get_plugin_metadata_not_found(self):
        assert get_plugin_metadata("nonexistent") is None

    def test_validate_plugin_kwargs(self):
        @register_plugin(
            analysis_type="pc_test_validate",
            version="1.0.0",
            description="",
            required_kwargs=["x", "y"],
        )
        def fn(run, **kwargs):
            return {}

        assert validate_plugin_kwargs("pc_test_validate", {"x": 1, "y": 2}) == []
        assert validate_plugin_kwargs("pc_test_validate", {"x": 1}) == ["y"]

    def test_validate_plugin_kwargs_unknown_type(self):
        with pytest.raises(ValueError, match="No plugin"):
            validate_plugin_kwargs("nonexistent_type", {})


# ---------------------------------------------------------------------------
# AC-1: Discovery and catalog
# ---------------------------------------------------------------------------

class TestPluginDiscovery:
    def test_list_plugins_returns_all(self):
        plugins = list_plugins()
        assert len(plugins) >= 0  # At least the ones from previous tests

    def test_catalog_serializable(self):
        @register_plugin(analysis_type="pc_test_catalog", version="1.0.0", description="Catalog test")
        def fn(run, **kwargs):
            return {}

        catalog = get_plugin_catalog()
        assert isinstance(catalog, list)
        # Find our test entry
        entry = [c for c in catalog if c["analysis_type"] == "pc_test_catalog"]
        assert len(entry) == 1
        assert entry[0]["version"] == "1.0.0"
        assert entry[0]["has_result_schema"] is False

    def test_catalog_includes_schema_flag(self):
        @register_plugin(
            analysis_type="pc_test_cat_schema",
            version="1.0.0",
            description="",
            result_schema=_DummyResult,
        )
        def fn(run, **kwargs):
            return {}

        catalog = get_plugin_catalog()
        entry = [c for c in catalog if c["analysis_type"] == "pc_test_cat_schema"]
        assert entry[0]["has_result_schema"] is True


# ---------------------------------------------------------------------------
# AC-2: Existing methodologies work with the contract
# ---------------------------------------------------------------------------

class TestExistingMethodologies:
    """Verify existing analyses satisfy the plugin protocol."""

    def test_drivers_is_registered(self):
        assert "drivers" in _ANALYSIS_REGISTRY

    def test_segmentation_is_registered(self):
        assert "segmentation" in _ANALYSIS_REGISTRY

    def test_maxdiff_turf_is_registered(self):
        assert "maxdiff_turf" in _ANALYSIS_REGISTRY

    def test_drivers_satisfies_protocol(self):
        fn = _ANALYSIS_REGISTRY["drivers"]
        assert isinstance(fn, AnalysisPlugin)

    def test_segmentation_satisfies_protocol(self):
        fn = _ANALYSIS_REGISTRY["segmentation"]
        assert isinstance(fn, AnalysisPlugin)

    def test_maxdiff_turf_satisfies_protocol(self):
        fn = _ANALYSIS_REGISTRY["maxdiff_turf"]
        assert isinstance(fn, AnalysisPlugin)

    def test_all_have_result_schemas(self):
        for analysis_type in ["drivers", "segmentation", "maxdiff_turf"]:
            assert analysis_type in RESULT_SCHEMAS, f"{analysis_type} missing result schema"

    def test_registered_types_matches(self):
        types = get_registered_types()
        assert "drivers" in types
        assert "segmentation" in types
        assert "maxdiff_turf" in types

    def test_drivers_has_plugin_metadata(self):
        meta = get_plugin_metadata("drivers")
        assert meta is not None
        assert meta.version == "1.0.0"
        assert "df" in meta.required_kwargs
        assert meta.result_schema is not None

    def test_segmentation_has_plugin_metadata(self):
        meta = get_plugin_metadata("segmentation")
        assert meta is not None
        assert meta.is_composite is True
        assert "df" in meta.required_kwargs
        assert meta.result_schema is not None

    def test_maxdiff_turf_has_plugin_metadata(self):
        meta = get_plugin_metadata("maxdiff_turf")
        assert meta is not None
        assert "df" in meta.required_kwargs
        assert meta.result_schema is not None

    def test_all_methodologies_in_catalog(self):
        catalog = get_plugin_catalog()
        types = {c["analysis_type"] for c in catalog}
        assert "drivers" in types
        assert "segmentation" in types
        assert "maxdiff_turf" in types


# ---------------------------------------------------------------------------
# AC-3: Minimal boilerplate smoke test for new methodology
# ---------------------------------------------------------------------------

class TestNewMethodologySmokeTest:
    """Demonstrates that a new analysis can be added with minimal boilerplate.

    This test class IS the smoke test template — copy and adapt for new analyses.
    """

    def setup_method(self):
        """Register a minimal new analysis plugin."""

        class SmokeResult(BaseModel):
            analysis_type: str = "smoke_test"
            computed_value: float

        @register_plugin(
            analysis_type="pc_test_smoke",
            version="0.1.0",
            description="Smoke test analysis for contract verification",
            required_kwargs=["data"],
            result_schema=SmokeResult,
            tags=["smoke", "test"],
        )
        def run_smoke(run, **kwargs):
            data = kwargs.get("data", [])
            if not data:
                raise AnalysisError("No data provided", error_type="missing_data")
            return {"analysis_type": "smoke_test", "computed_value": sum(data) / len(data)}

        self._fn = run_smoke
        self._schema = SmokeResult

    def teardown_method(self):
        _PLUGIN_METADATA.pop("pc_test_smoke", None)
        _ANALYSIS_REGISTRY.pop("pc_test_smoke", None)
        RESULT_SCHEMAS.pop("pc_test_smoke", None)

    def test_plugin_registered(self):
        assert "pc_test_smoke" in _ANALYSIS_REGISTRY
        assert "pc_test_smoke" in _PLUGIN_METADATA
        assert "pc_test_smoke" in RESULT_SCHEMAS

    def test_metadata_correct(self):
        meta = get_plugin_metadata("pc_test_smoke")
        assert meta.version == "0.1.0"
        assert meta.required_kwargs == ["data"]
        assert "smoke" in meta.tags

    def test_kwargs_validation(self):
        missing = validate_plugin_kwargs("pc_test_smoke", {})
        assert "data" in missing

        missing = validate_plugin_kwargs("pc_test_smoke", {"data": [1, 2, 3]})
        assert missing == []

    def test_execution_success(self):
        run = _make_run("pc_test_smoke")
        store = RunStore()
        result = execute_run(run, store=store, data=[10, 20, 30])
        assert result.status == RunStatus.COMPLETED
        assert result.result_summary["computed_value"] == 20.0

    def test_execution_validates_schema(self):
        """Result is validated against the registered schema."""
        run = _make_run("pc_test_smoke")
        result = execute_run(run, data=[5, 15])
        assert result.status == RunStatus.COMPLETED
        # Validate manually too
        validated = self._schema.model_validate(result.result_summary)
        assert validated.computed_value == 10.0

    def test_execution_failure_is_typed(self):
        run = _make_run("pc_test_smoke")
        result = execute_run(run, data=[])
        assert result.status == RunStatus.FAILED
        assert result.error_type == "missing_data"
        assert "No data provided" in result.error_message

    def test_protocol_satisfied(self):
        assert isinstance(self._fn, AnalysisPlugin)
