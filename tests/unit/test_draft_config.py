"""Contract tests for methodology/section selector (P03-01).

AC-1: All supported methodologies are selectable.
AC-2: Section options reflect methodology matrix.
AC-3: Selections persist in draft metadata.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from packages.shared.assistant_context import Methodology
from packages.shared.draft_config import DraftConfig, DraftStore
from packages.shared.section_taxonomy import METHODOLOGY_MATRIX, get_matrix

client = TestClient(app)

ALL_METHODOLOGIES = list(Methodology)


# ---------------------------------------------------------------------------
# AC-1: All supported methodologies are selectable
# ---------------------------------------------------------------------------

class TestMethodologySelection:
    @pytest.mark.parametrize("meth", ALL_METHODOLOGIES)
    def test_create_draft_for_each_methodology(self, meth: Methodology):
        store = DraftStore()
        draft = store.create("proj-001", meth)
        assert draft.methodology == meth

    def test_list_methodologies_returns_all_eight(self):
        resp = client.get("/api/v1/drafts/methodologies")
        assert resp.status_code == 200
        meths = resp.json()["methodologies"]
        assert len(meths) == 8
        values = {m["value"] for m in meths}
        for m in ALL_METHODOLOGIES:
            assert m.value in values

    @pytest.mark.parametrize("meth", ALL_METHODOLOGIES)
    def test_get_sections_endpoint_for_each(self, meth: Methodology):
        resp = client.get(f"/api/v1/drafts/methodologies/{meth.value}/sections")
        assert resp.status_code == 200
        body = resp.json()
        assert body["methodology"] == meth.value
        assert len(body["sections"]) >= 3

    def test_invalid_methodology_returns_400(self):
        resp = client.get("/api/v1/drafts/methodologies/fake_method/sections")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# AC-2: Section options reflect methodology matrix
# ---------------------------------------------------------------------------

class TestSectionOptions:
    @pytest.mark.parametrize("meth", ALL_METHODOLOGIES)
    def test_draft_sections_match_matrix(self, meth: Methodology):
        store = DraftStore()
        draft = store.create("proj-001", meth)
        matrix = get_matrix(meth)
        expected = [st.value for st in matrix.section_order]
        assert draft.selected_sections == expected

    @pytest.mark.parametrize("meth", ALL_METHODOLOGIES)
    def test_section_options_have_required_keys(self, meth: Methodology):
        store = DraftStore()
        draft = store.create("proj-001", meth)
        options = draft.get_section_options()
        for opt in options:
            assert "section_type" in opt
            assert "label" in opt
            assert "required" in opt
            assert "selected" in opt
            assert "typical_questions" in opt

    @pytest.mark.parametrize("meth", ALL_METHODOLOGIES)
    def test_all_sections_initially_selected(self, meth: Methodology):
        store = DraftStore()
        draft = store.create("proj-001", meth)
        options = draft.get_section_options()
        assert all(opt["selected"] for opt in options)

    @pytest.mark.parametrize("meth", ALL_METHODOLOGIES)
    def test_required_sections_flagged(self, meth: Methodology):
        store = DraftStore()
        draft = store.create("proj-001", meth)
        matrix = get_matrix(meth)
        required_types = {st.value for st in matrix.required_sections()}
        options = draft.get_section_options()
        for opt in options:
            if opt["section_type"] in required_types:
                assert opt["required"] is True

    def test_changing_methodology_resets_sections(self):
        store = DraftStore()
        draft = store.create("proj-001", Methodology.SEGMENTATION)
        seg_sections = list(draft.selected_sections)
        draft.update_methodology(Methodology.MAXDIFF)
        assert draft.selected_sections != seg_sections
        matrix = get_matrix(Methodology.MAXDIFF)
        assert draft.selected_sections == [st.value for st in matrix.section_order]

    def test_deselect_optional_section(self):
        store = DraftStore()
        draft = store.create("proj-001", Methodology.SEGMENTATION)
        matrix = get_matrix(Methodology.SEGMENTATION)
        # Keep only required sections + one optional
        required = [st.value for st in matrix.required_sections()]
        errors = draft.update_sections(required)
        assert errors == []
        assert set(draft.selected_sections) == set(required)

    def test_cannot_deselect_required_section(self):
        store = DraftStore()
        draft = store.create("proj-001", Methodology.SEGMENTATION)
        # Try to select without the screener (required)
        errors = draft.update_sections(["attitudes", "demographics"])
        assert len(errors) > 0
        assert any("screener" in e.lower() for e in errors)

    def test_invalid_section_rejected(self):
        store = DraftStore()
        draft = store.create("proj-001", Methodology.SEGMENTATION)
        errors = draft.update_sections(["screener", "demographics", "fake_section"])
        assert any("fake_section" in e for e in errors)


# ---------------------------------------------------------------------------
# AC-3: Selections persist in draft metadata
# ---------------------------------------------------------------------------

class TestDraftPersistence:
    def test_draft_persists_in_store(self):
        store = DraftStore()
        draft = store.create("proj-001", Methodology.SEGMENTATION)
        retrieved = store.get(draft.draft_id)
        assert retrieved is not None
        assert retrieved.draft_id == draft.draft_id
        assert retrieved.methodology == Methodology.SEGMENTATION

    def test_updated_at_changes_on_edit(self):
        store = DraftStore()
        draft = store.create("proj-001", Methodology.SEGMENTATION)
        original_updated = draft.updated_at
        draft.update_methodology(Methodology.MAXDIFF)
        assert draft.updated_at >= original_updated

    def test_get_by_project(self):
        store = DraftStore()
        store.create("proj-a", Methodology.SEGMENTATION)
        store.create("proj-b", Methodology.MAXDIFF)
        result = store.get_by_project("proj-a")
        assert result is not None
        assert result.project_id == "proj-a"

    def test_for_generation_output(self):
        store = DraftStore()
        draft = store.create("proj-001", Methodology.SEGMENTATION)
        config = draft.for_generation()
        assert config["methodology"] == "segmentation"
        assert config["project_id"] == "proj-001"
        assert len(config["sections"]) >= 3
        assert "loi_range" in config
        for sec in config["sections"]:
            assert "section_type" in sec
            assert "required_fields" in sec
            assert "validation_rules" in sec


# ---------------------------------------------------------------------------
# API integration
# ---------------------------------------------------------------------------

class TestDraftAPI:
    def test_create_draft_endpoint(self):
        resp = client.post("/api/v1/drafts/", json={
            "project_id": "proj-api-001",
            "methodology": "segmentation",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["methodology"] == "segmentation"
        assert len(body["selected_sections"]) >= 3
        assert len(body["section_options"]) >= 3

    def test_create_draft_bad_methodology(self):
        resp = client.post("/api/v1/drafts/", json={
            "project_id": "proj-001",
            "methodology": "fake",
        })
        assert resp.status_code == 400

    def test_get_draft_endpoint(self):
        create = client.post("/api/v1/drafts/", json={
            "project_id": "proj-api-002",
            "methodology": "drivers",
        })
        draft_id = create.json()["draft_id"]
        resp = client.get(f"/api/v1/drafts/{draft_id}")
        assert resp.status_code == 200
        assert resp.json()["methodology"] == "drivers"

    def test_get_nonexistent_draft(self):
        resp = client.get("/api/v1/drafts/nonexistent")
        assert resp.status_code == 404

    def test_update_methodology_endpoint(self):
        create = client.post("/api/v1/drafts/", json={
            "project_id": "proj-api-003",
            "methodology": "segmentation",
        })
        draft_id = create.json()["draft_id"]
        resp = client.patch(f"/api/v1/drafts/{draft_id}/methodology", json={
            "methodology": "maxdiff",
        })
        assert resp.status_code == 200
        assert resp.json()["methodology"] == "maxdiff"

    def test_update_sections_endpoint(self):
        create = client.post("/api/v1/drafts/", json={
            "project_id": "proj-api-004",
            "methodology": "segmentation",
        })
        draft_id = create.json()["draft_id"]
        matrix = get_matrix(Methodology.SEGMENTATION)
        required = [st.value for st in matrix.required_sections()]

        resp = client.patch(f"/api/v1/drafts/{draft_id}/sections", json={
            "selected_sections": required,
        })
        assert resp.status_code == 200
        assert set(resp.json()["selected_sections"]) == set(required)

    def test_update_sections_invalid_returns_422(self):
        create = client.post("/api/v1/drafts/", json={
            "project_id": "proj-api-005",
            "methodology": "segmentation",
        })
        draft_id = create.json()["draft_id"]
        resp = client.patch(f"/api/v1/drafts/{draft_id}/sections", json={
            "selected_sections": ["demographics"],  # missing required screener
        })
        assert resp.status_code == 422

    def test_generation_config_endpoint(self):
        create = client.post("/api/v1/drafts/", json={
            "project_id": "proj-api-006",
            "methodology": "attitude_usage",
        })
        draft_id = create.json()["draft_id"]
        resp = client.get(f"/api/v1/drafts/{draft_id}/generation-config")
        assert resp.status_code == 200
        body = resp.json()
        assert body["methodology"] == "attitude_usage"
        assert len(body["sections"]) >= 3
