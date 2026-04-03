"""Contract tests for analysis run orchestrator (P07-01).

AC-1: Statuses: queued/running/failed/completed.
AC-2: Run metadata includes input and config versions.
AC-3: Failure messages are actionable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.survey_analysis.run_orchestrator import (
    AnalysisError,
    AnalysisRun,
    RunConfig,
    RunStatus,
    RunStore,
    RunVersions,
    _ANALYSIS_REGISTRY,
    create_run,
    execute_run,
    get_registered_types,
    register_analysis,
    save_run_manifest,
)


def _config(analysis_type: str = "test_analysis") -> RunConfig:
    return RunConfig(analysis_type=analysis_type, parameters={"k": 5})


def _versions() -> RunVersions:
    return RunVersions(
        questionnaire_id="qre-001",
        questionnaire_version=3,
        mapping_id="map-001",
        mapping_version=2,
        data_file_hash="sha256:abc123",
    )


# Register test analysis functions
@register_analysis("test_success")
def _analysis_success(run: AnalysisRun, **kwargs) -> dict:
    return {"clusters": 5, "silhouette": 0.45}


@register_analysis("test_fail")
def _analysis_fail(run: AnalysisRun, **kwargs) -> dict:
    raise AnalysisError(
        "Insufficient variance in attitude battery. Need at least 15 items with variance > 0.5. "
        "Currently 8 items meet this threshold.",
        error_type="insufficient_variance",
    )


@register_analysis("test_crash")
def _analysis_crash(run: AnalysisRun, **kwargs) -> dict:
    raise RuntimeError("Unexpected pandas error")


# ---------------------------------------------------------------------------
# AC-1: Statuses: queued/running/failed/completed
# ---------------------------------------------------------------------------

class TestStatusLifecycle:
    def test_create_run_starts_queued(self):
        run = create_run("proj-001", _config("test_success"), _versions())
        assert run.status == RunStatus.QUEUED

    def test_successful_run_transitions_to_completed(self):
        run = create_run("proj-001", _config("test_success"), _versions())
        result = execute_run(run)
        assert result.status == RunStatus.COMPLETED

    def test_failed_run_transitions_to_failed(self):
        run = create_run("proj-001", _config("test_fail"), _versions())
        result = execute_run(run)
        assert result.status == RunStatus.FAILED

    def test_crash_transitions_to_failed(self):
        run = create_run("proj-001", _config("test_crash"), _versions())
        result = execute_run(run)
        assert result.status == RunStatus.FAILED

    def test_unknown_type_transitions_to_failed(self):
        run = create_run("proj-001", _config("nonexistent_type"), _versions())
        result = execute_run(run)
        assert result.status == RunStatus.FAILED

    def test_cannot_execute_non_queued_run(self):
        run = create_run("proj-001", _config("test_success"), _versions())
        execute_run(run)  # now COMPLETED
        with pytest.raises(ValueError, match="QUEUED"):
            execute_run(run)

    def test_completed_run_has_timestamps(self):
        run = create_run("proj-001", _config("test_success"), _versions())
        execute_run(run)
        assert run.started_at is not None
        assert run.completed_at is not None
        assert run.duration_ms is not None
        assert run.duration_ms >= 0

    def test_failed_run_has_timestamps(self):
        run = create_run("proj-001", _config("test_fail"), _versions())
        execute_run(run)
        assert run.started_at is not None
        assert run.completed_at is not None

    def test_is_terminal(self):
        run = create_run("proj-001", _config("test_success"), _versions())
        assert not run.is_terminal()
        execute_run(run)
        assert run.is_terminal()


# ---------------------------------------------------------------------------
# AC-2: Run metadata includes input and config versions
# ---------------------------------------------------------------------------

class TestVersionProvenance:
    def test_run_stores_versions(self):
        run = create_run("proj-001", _config("test_success"), _versions())
        assert run.versions.questionnaire_id == "qre-001"
        assert run.versions.questionnaire_version == 3
        assert run.versions.mapping_id == "map-001"
        assert run.versions.mapping_version == 2
        assert run.versions.data_file_hash == "sha256:abc123"

    def test_run_stores_config(self):
        run = create_run("proj-001", _config("test_success"), _versions())
        assert run.config.analysis_type == "test_success"
        assert run.config.parameters["k"] == 5

    def test_provenance_dict(self):
        run = create_run("proj-001", _config("test_success"), _versions())
        execute_run(run)
        prov = run.provenance()
        assert prov["run_id"] == run.run_id
        assert prov["project_id"] == "proj-001"
        assert prov["analysis_type"] == "test_success"
        assert prov["status"] == "completed"
        assert prov["versions"]["questionnaire_version"] == 3
        assert prov["versions"]["mapping_version"] == 2
        assert prov["parameters"]["k"] == 5
        assert prov["started_at"] is not None
        assert prov["completed_at"] is not None
        assert prov["duration_ms"] is not None

    def test_result_summary_on_success(self):
        run = create_run("proj-001", _config("test_success"), _versions())
        execute_run(run)
        assert run.result_summary is not None
        assert run.result_summary["clusters"] == 5
        assert run.result_summary["silhouette"] == 0.45


# ---------------------------------------------------------------------------
# AC-3: Failure messages are actionable
# ---------------------------------------------------------------------------

class TestActionableFailures:
    def test_analysis_error_has_message(self):
        run = create_run("proj-001", _config("test_fail"), _versions())
        execute_run(run)
        assert run.error_message is not None
        assert "variance" in run.error_message.lower()
        assert "15 items" in run.error_message

    def test_analysis_error_has_type(self):
        run = create_run("proj-001", _config("test_fail"), _versions())
        execute_run(run)
        assert run.error_type == "insufficient_variance"

    def test_unexpected_error_has_message(self):
        run = create_run("proj-001", _config("test_crash"), _versions())
        execute_run(run)
        assert run.error_message is not None
        assert "Unexpected error" in run.error_message
        assert run.error_type == "unexpected_error"

    def test_unknown_type_error_lists_registered(self):
        run = create_run("proj-001", _config("nonexistent"), _versions())
        execute_run(run)
        assert "Unknown analysis type" in run.error_message
        assert run.error_type == "unknown_analysis_type"
        # Should list registered types
        assert "test_success" in run.error_message

    def test_success_has_no_error(self):
        run = create_run("proj-001", _config("test_success"), _versions())
        execute_run(run)
        assert run.error_message is None
        assert run.error_type is None


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class TestRunStore:
    def test_save_and_get(self):
        store = RunStore()
        run = create_run("proj-001", _config("test_success"), _versions(), store=store)
        retrieved = store.get(run.run_id)
        assert retrieved is not None
        assert retrieved.run_id == run.run_id

    def test_get_by_project(self):
        store = RunStore()
        create_run("proj-a", _config(), _versions(), store=store)
        create_run("proj-a", _config(), _versions(), store=store)
        create_run("proj-b", _config(), _versions(), store=store)
        assert len(store.get_by_project("proj-a")) == 2
        assert len(store.get_by_project("proj-b")) == 1

    def test_get_by_status(self):
        store = RunStore()
        r1 = create_run("proj-001", _config("test_success"), _versions(), store=store)
        r2 = create_run("proj-001", _config("test_fail"), _versions(), store=store)
        execute_run(r1, store=store)
        execute_run(r2, store=store)
        assert len(store.get_by_status(RunStatus.COMPLETED)) == 1
        assert len(store.get_by_status(RunStatus.FAILED)) == 1
        assert len(store.get_by_status(RunStatus.QUEUED)) == 0

    def test_store_updates_on_execute(self):
        store = RunStore()
        run = create_run("proj-001", _config("test_success"), _versions(), store=store)
        assert store.get(run.run_id).status == RunStatus.QUEUED
        execute_run(run, store=store)
        assert store.get(run.run_id).status == RunStatus.COMPLETED

    def test_count(self):
        store = RunStore()
        assert store.count == 0
        create_run("proj-001", _config(), _versions(), store=store)
        assert store.count == 1

    def test_get_nonexistent_returns_none(self):
        store = RunStore()
        assert store.get("nonexistent") is None


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_registered_types(self):
        types = get_registered_types()
        assert "test_success" in types
        assert "test_fail" in types
        assert "test_crash" in types

    def test_register_new_type(self):
        @register_analysis("custom_test")
        def _custom(run, **kw):
            return {"custom": True}

        assert "custom_test" in get_registered_types()
        run = create_run("proj-001", RunConfig(analysis_type="custom_test"), _versions())
        execute_run(run)
        assert run.status == RunStatus.COMPLETED
        assert run.result_summary["custom"] is True

        # Cleanup
        del _ANALYSIS_REGISTRY["custom_test"]


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_save_manifest(self, tmp_path: Path):
        run = create_run("proj-001", _config("test_success"), _versions())
        execute_run(run)
        run_dir = save_run_manifest(run, tmp_path / "Runs")
        manifest = run_dir / "run_manifest.json"
        assert manifest.exists()
        data = json.loads(manifest.read_text())
        assert data["run_id"] == run.run_id
        assert data["status"] == "completed"
        assert data["versions"]["questionnaire_version"] == 3

    def test_run_id_unique(self):
        r1 = create_run("p", _config(), _versions())
        r2 = create_run("p", _config(), _versions())
        assert r1.run_id != r2.run_id
