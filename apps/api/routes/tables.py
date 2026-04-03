"""Table generation, QA, and copilot API routes."""

from __future__ import annotations

from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

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

# In-memory stores
_runs: dict[str, TableRunResult] = {}
_qa_reports: dict[str, QAReport] = {}
_copilot_sessions: dict[str, QACopilotSession] = {}


class GenerateRequest(BaseModel):
    project_id: str
    mapping_id: str
    mapping_version: int = 1
    questionnaire_version: int = 1
    variables: list[dict[str, Any]]
    data_rows: list[dict[str, Any]]
    config: TableConfig | None = None


@router.post("/generate")
def generate(body: GenerateRequest) -> dict[str, Any]:
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
    return {
        "run_id": result.run_id,
        "total_tables": result.total_tables,
        "provenance": result.provenance(),
    }


@router.post("/{run_id}/qa")
def qa_check(run_id: str) -> dict[str, Any]:
    """Run QA checks on a table generation run."""
    result = _runs.get(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found.")

    report = run_table_qa(result)
    _qa_reports[report.report_id] = report
    return {
        "report_id": report.report_id,
        "run_id": run_id,
        "passed": report.passed,
        "error_count": report.error_count,
        "warning_count": report.warning_count,
        "findings": report.for_ui(),
    }


@router.post("/{run_id}/qa-copilot")
def qa_copilot(run_id: str) -> dict[str, Any]:
    """Run QA copilot analysis on the latest QA report for a run."""
    # Find the QA report for this run
    report = next((r for r in _qa_reports.values() if r.run_id == run_id), None)
    if not report:
        raise HTTPException(status_code=404, detail="QA report not found. Run /qa first.")

    session = analyze_qa_report(report)
    _copilot_sessions[session.session_id] = session
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
