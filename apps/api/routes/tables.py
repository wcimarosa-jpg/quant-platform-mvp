"""Table generation, QA, and copilot API routes."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from apps.api.auth_deps import CurrentUser
from apps.api.resource_auth import record_ownership, require_owner
from packages.survey_analysis.table_generator import (
    TableConfig,
    TableGenerationError,
    TableRunResult,
    generate_tables,
    save_run,
)
from packages.survey_analysis.table_qa import QAReport, run_table_qa, save_qa_report
from packages.survey_analysis.table_qa_copilot import (
    DecisionStatus,
    QACopilotSession,
    analyze_qa_report,
    resolve_action,
)

router = APIRouter(prefix="/tables", tags=["tables"])

# In-memory stores with LRU eviction.
# TODO: Replace with database persistence in production.
_MAX_STORE_SIZE = 100


class _LRUStore(OrderedDict):
    """OrderedDict that evicts oldest entries when size exceeds _MAX_STORE_SIZE."""

    def __setitem__(self, key: str, value: Any) -> None:
        super().__setitem__(key, value)
        self.move_to_end(key)
        while len(self) > _MAX_STORE_SIZE:
            self.popitem(last=False)


_runs: _LRUStore = _LRUStore()
_qa_reports: _LRUStore = _LRUStore()
_copilot_sessions: _LRUStore = _LRUStore()

# Payload limits
_MAX_DATA_ROWS = 500_000
_MAX_VARIABLES = 1_000


class GenerateRequest(BaseModel):
    project_id: str
    mapping_id: str
    mapping_version: int = 1
    questionnaire_version: int = 1
    variables: list[dict[str, Any]] = Field(max_length=_MAX_VARIABLES)
    data_rows: list[dict[str, Any]] = Field(max_length=_MAX_DATA_ROWS)
    config: TableConfig | None = None


@router.post("/generate")
def generate(body: GenerateRequest, user: CurrentUser) -> dict[str, Any]:
    """Generate tables from inline data and variable mapping."""
    df = pd.DataFrame(body.data_rows)
    if df.empty:
        raise HTTPException(status_code=422, detail="data_rows is empty.")

    try:
        result = generate_tables(
            project_id=body.project_id,
            mapping_id=body.mapping_id,
            mapping_version=body.mapping_version,
            questionnaire_version=body.questionnaire_version,
            variables=body.variables,
            df=df,
            config=body.config,
        )
    except TableGenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    _runs[result.run_id] = result
    record_ownership(result.run_id, owner_id=user.sub, project_id=body.project_id)
    return {
        "run_id": result.run_id,
        "total_tables": result.total_tables,
        "provenance": result.provenance(),
    }


@router.post("/{run_id}/qa")
def qa_check(run_id: str, user: CurrentUser) -> dict[str, Any]:
    """Run QA checks on a table generation run."""
    result = _runs.get(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found.")
    require_owner(run_id, user)

    report = run_table_qa(result)
    _qa_reports[report.report_id] = report
    record_ownership(report.report_id, owner_id=user.sub)
    return {
        "report_id": report.report_id,
        "run_id": run_id,
        "passed": report.passed,
        "error_count": report.error_count,
        "warning_count": report.warning_count,
        "findings": report.for_ui(),
    }


@router.post("/{run_id}/qa-copilot")
def qa_copilot(run_id: str, user: CurrentUser) -> dict[str, Any]:
    """Run QA copilot analysis on the latest QA report for a run."""
    require_owner(run_id, user)
    report = next((r for r in _qa_reports.values() if r.run_id == run_id), None)
    if not report:
        raise HTTPException(status_code=404, detail="QA report not found. Run /qa first.")

    session = analyze_qa_report(report)
    _copilot_sessions[session.session_id] = session
    record_ownership(session.session_id, owner_id=user.sub)
    return {
        "session_id": session.session_id,
        "report_id": report.report_id,
        "explanations": [e.model_dump() for e in session.explanations],
        "actions": [
            {
                "action_id": a.action_id,
                "finding_id": a.finding_id,
                "action_type": a.action_type.value,
                "description": a.description,
                "status": a.status.value,
            }
            for a in session.actions
        ],
        "all_resolved": session.all_resolved(),
    }
