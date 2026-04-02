"""Contract tests for event logging and provenance (P01-04).

AC-1: Events captured for create/update/upload/run/export actions.
AC-2: Assistant actions include prompt-context metadata.
AC-3: Logs are queryable by project and run.
"""

from __future__ import annotations

import pytest

from packages.shared.event_log import (
    ArtifactRef,
    AssistantMetadata,
    Event,
    EventAction,
    EventCategory,
    EventStore,
)


@pytest.fixture
def store() -> EventStore:
    return EventStore()


# ---------------------------------------------------------------------------
# AC-1: Events captured for create/update/upload/run/export actions
# ---------------------------------------------------------------------------

class TestEventCapture:
    @pytest.mark.parametrize("action", [
        EventAction.PROJECT_CREATED,
        EventAction.PROJECT_UPDATED,
    ])
    def test_create_update_events(self, store: EventStore, action: EventAction):
        evt = store.emit(
            project_id="proj-001",
            action=action,
            actor="user",
            description=f"Test {action.value}",
        )
        assert evt.action == action
        assert evt.project_id == "proj-001"
        assert evt.category == EventCategory.PROJECT

    @pytest.mark.parametrize("action", [
        EventAction.BRIEF_UPLOADED,
        EventAction.DATA_UPLOADED,
    ])
    def test_upload_events(self, store: EventStore, action: EventAction):
        evt = store.emit(
            project_id="proj-001",
            action=action,
            actor="user",
            description=f"Test {action.value}",
            artifacts=[ArtifactRef(artifact_type="data_file", artifact_id="file-001")],
        )
        assert evt.action == action
        assert len(evt.artifacts) == 1

    @pytest.mark.parametrize("action", [
        EventAction.RUN_QUEUED,
        EventAction.RUN_STARTED,
        EventAction.RUN_COMPLETED,
        EventAction.RUN_FAILED,
    ])
    def test_run_events(self, store: EventStore, action: EventAction):
        evt = store.emit(
            project_id="proj-001",
            action=action,
            actor="system",
            description=f"Test {action.value}",
            run_id="run-001",
        )
        assert evt.action == action
        assert evt.run_id == "run-001"
        assert evt.category == EventCategory.ANALYSIS

    @pytest.mark.parametrize("action", [
        EventAction.EXPORT_GENERATED,
        EventAction.EXPORT_DOWNLOADED,
    ])
    def test_export_events(self, store: EventStore, action: EventAction):
        evt = store.emit(
            project_id="proj-001",
            action=action,
            actor="user",
            description=f"Test {action.value}",
            artifacts=[ArtifactRef(artifact_type="export", artifact_id="exp-001")],
        )
        assert evt.action == action
        assert evt.category == EventCategory.EXPORT

    def test_all_action_types_have_categories(self):
        """Every EventAction must resolve to a valid EventCategory."""
        store = EventStore()
        for action in EventAction:
            evt = store.emit(
                project_id="proj-test",
                action=action,
                actor="test",
                description=f"Test {action.value}",
            )
            assert evt.category in EventCategory

    def test_event_id_is_unique(self, store: EventStore):
        ids = set()
        for i in range(10):
            evt = store.emit(
                project_id="proj-001",
                action=EventAction.PROJECT_CREATED,
                actor="user",
                description=f"Event {i}",
            )
            ids.add(evt.event_id)
        assert len(ids) == 10

    def test_event_has_timestamp(self, store: EventStore):
        evt = store.emit(
            project_id="proj-001",
            action=EventAction.PROJECT_CREATED,
            actor="user",
            description="test",
        )
        assert evt.timestamp is not None

    def test_event_with_artifact_refs(self, store: EventStore):
        evt = store.emit(
            project_id="proj-001",
            action=EventAction.QUESTIONNAIRE_GENERATED,
            actor="assistant",
            description="Generated questionnaire v1",
            artifacts=[
                ArtifactRef(artifact_type="questionnaire", artifact_id="qre-001", version=1),
            ],
        )
        assert evt.artifacts[0].artifact_id == "qre-001"
        assert evt.artifacts[0].version == 1

    def test_event_with_multiple_artifacts(self, store: EventStore):
        evt = store.emit(
            project_id="proj-001",
            action=EventAction.MAPPING_GENERATED,
            actor="assistant",
            description="Auto-mapped columns",
            artifacts=[
                ArtifactRef(artifact_type="mapping", artifact_id="map-001", version=1),
                ArtifactRef(artifact_type="data_file", artifact_id="file-001"),
            ],
        )
        assert len(evt.artifacts) == 2


# ---------------------------------------------------------------------------
# AC-2: Assistant actions include prompt-context metadata
# ---------------------------------------------------------------------------

class TestAssistantMetadata:
    def test_assistant_event_has_metadata(self, store: EventStore):
        meta = AssistantMetadata(
            context_hash="abcdef0123456789",
            action="generate",
            screen="questionnaire_editor",
            input_summary="Generate screener section",
            output_summary="Generated 5 questions",
            duration_ms=1200,
            model="claude-opus-4-6",
        )
        evt = store.emit(
            project_id="proj-001",
            action=EventAction.ASSISTANT_INVOKED,
            actor="assistant",
            description="Assistant generated screener",
            assistant_metadata=meta,
        )
        assert evt.assistant_metadata is not None
        assert evt.assistant_metadata.context_hash == "abcdef0123456789"
        assert evt.assistant_metadata.action == "generate"
        assert evt.assistant_metadata.screen == "questionnaire_editor"
        assert evt.assistant_metadata.duration_ms == 1200
        assert evt.assistant_metadata.model == "claude-opus-4-6"

    def test_assistant_completed_event(self, store: EventStore):
        meta = AssistantMetadata(
            context_hash="1234567890abcdef",
            action="explain",
            screen="analysis_results",
            input_summary="Explain K-Means output",
            output_summary="Generated 3-paragraph narrative",
            duration_ms=2500,
        )
        evt = store.emit(
            project_id="proj-001",
            action=EventAction.ASSISTANT_COMPLETED,
            actor="assistant",
            description="Assistant explanation complete",
            assistant_metadata=meta,
        )
        assert evt.action == EventAction.ASSISTANT_COMPLETED
        assert evt.assistant_metadata.output_summary == "Generated 3-paragraph narrative"

    def test_assistant_failed_event(self, store: EventStore):
        meta = AssistantMetadata(
            context_hash="fedcba9876543210",
            action="generate",
            screen="questionnaire_editor",
            input_summary="Generate attitudes battery",
            output_summary="ERROR: LLM rate limit exceeded",
        )
        evt = store.emit(
            project_id="proj-001",
            action=EventAction.ASSISTANT_FAILED,
            actor="assistant",
            description="Assistant generation failed",
            assistant_metadata=meta,
        )
        assert evt.action == EventAction.ASSISTANT_FAILED
        assert "rate limit" in evt.assistant_metadata.output_summary

    def test_non_assistant_event_has_no_metadata(self, store: EventStore):
        evt = store.emit(
            project_id="proj-001",
            action=EventAction.PROJECT_CREATED,
            actor="user",
            description="User created project",
        )
        assert evt.assistant_metadata is None

    def test_metadata_fields_all_present(self):
        meta = AssistantMetadata(
            context_hash="abc123",
            action="suggest",
            screen="mapping_editor",
            input_summary="Suggest column mapping",
        )
        assert meta.context_hash
        assert meta.action
        assert meta.screen
        assert meta.input_summary
        # Optional fields default to None
        assert meta.output_summary is None
        assert meta.duration_ms is None
        assert meta.model is None


# ---------------------------------------------------------------------------
# AC-3: Logs queryable by project and run
# ---------------------------------------------------------------------------

class TestQueries:
    def _seed(self, store: EventStore) -> None:
        """Seed store with events across two projects and two runs."""
        store.emit(project_id="proj-a", action=EventAction.PROJECT_CREATED, actor="user", description="Create A")
        store.emit(project_id="proj-a", action=EventAction.BRIEF_UPLOADED, actor="user", description="Upload brief A",
                   artifacts=[ArtifactRef(artifact_type="brief", artifact_id="brief-a1")])
        store.emit(project_id="proj-a", action=EventAction.RUN_STARTED, actor="system", description="Run A1", run_id="run-a1")
        store.emit(project_id="proj-a", action=EventAction.RUN_COMPLETED, actor="system", description="Run A1 done", run_id="run-a1")
        store.emit(project_id="proj-a", action=EventAction.RUN_STARTED, actor="system", description="Run A2", run_id="run-a2")
        store.emit(project_id="proj-b", action=EventAction.PROJECT_CREATED, actor="user", description="Create B")
        store.emit(project_id="proj-b", action=EventAction.DATA_UPLOADED, actor="user", description="Upload data B",
                   artifacts=[ArtifactRef(artifact_type="data_file", artifact_id="file-b1")])

    def test_by_project_returns_correct_events(self, store: EventStore):
        self._seed(store)
        a_events = store.by_project("proj-a")
        b_events = store.by_project("proj-b")
        assert len(a_events) == 5
        assert len(b_events) == 2
        assert all(e.project_id == "proj-a" for e in a_events)

    def test_by_project_newest_first(self, store: EventStore):
        self._seed(store)
        events = store.by_project("proj-a")
        # First event should be the newest (run-a2)
        assert events[0].description == "Run A2"

    def test_by_project_respects_limit(self, store: EventStore):
        self._seed(store)
        events = store.by_project("proj-a", limit=2)
        assert len(events) == 2

    def test_by_run_returns_linked_events(self, store: EventStore):
        self._seed(store)
        run_events = store.by_run("run-a1")
        assert len(run_events) == 2
        assert all(e.run_id == "run-a1" for e in run_events)

    def test_by_run_empty_for_unknown(self, store: EventStore):
        self._seed(store)
        assert store.by_run("run-nonexistent") == []

    def test_by_action(self, store: EventStore):
        self._seed(store)
        created = store.by_action(EventAction.PROJECT_CREATED)
        assert len(created) == 2  # proj-a and proj-b

    def test_by_action_with_project_filter(self, store: EventStore):
        self._seed(store)
        created = store.by_action(EventAction.PROJECT_CREATED, project_id="proj-a")
        assert len(created) == 1

    def test_by_category(self, store: EventStore):
        self._seed(store)
        analysis_events = store.by_category(EventCategory.ANALYSIS)
        assert len(analysis_events) == 3  # 2 starts + 1 complete

    def test_by_category_with_project_filter(self, store: EventStore):
        self._seed(store)
        data_events = store.by_category(EventCategory.DATA, project_id="proj-b")
        assert len(data_events) == 1

    def test_by_artifact(self, store: EventStore):
        self._seed(store)
        brief_events = store.by_artifact("brief-a1")
        assert len(brief_events) == 1
        assert brief_events[0].action == EventAction.BRIEF_UPLOADED

    def test_count(self, store: EventStore):
        assert store.count == 0
        self._seed(store)
        assert store.count == 7

    def test_all_newest_first(self, store: EventStore):
        self._seed(store)
        events = store.all()
        assert len(events) == 7
        assert events[0].description == "Upload data B"  # last seeded


# ---------------------------------------------------------------------------
# Extra / edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_extra_field_passthrough(self, store: EventStore):
        evt = store.emit(
            project_id="proj-001",
            action=EventAction.EXPORT_GENERATED,
            actor="user",
            description="DOCX export",
            extra={"format": "docx", "pages": 12},
        )
        assert evt.extra["format"] == "docx"

    def test_empty_project_returns_empty(self, store: EventStore):
        assert store.by_project("nonexistent") == []

    def test_event_is_immutable(self, store: EventStore):
        evt = store.emit(
            project_id="proj-001",
            action=EventAction.PROJECT_CREATED,
            actor="user",
            description="test immutability",
        )
        with pytest.raises(Exception):  # Pydantic frozen raises ValidationError
            evt.action = EventAction.RUN_FAILED

    def test_artifact_ref_is_immutable(self):
        ref = ArtifactRef(artifact_type="data_file", artifact_id="file-001")
        with pytest.raises(Exception):
            ref.artifact_id = "tampered"

    def test_section_regenerated_maps_to_questionnaire_category(self, store: EventStore):
        evt = store.emit(
            project_id="proj-001",
            action=EventAction.SECTION_REGENERATED,
            actor="assistant",
            description="Regenerated screener",
        )
        assert evt.category == EventCategory.QUESTIONNAIRE
