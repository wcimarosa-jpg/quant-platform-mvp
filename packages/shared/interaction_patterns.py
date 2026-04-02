"""AI-first UI interaction patterns v1.

Defines the copilot panel behavior, approval checkpoints, and fallback
manual paths for every major screen in the platform. Consumable by
frontend components and backend orchestration logic.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .assistant_context import WorkflowStage

PATTERNS_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Screens — every major UI surface
# ---------------------------------------------------------------------------

class Screen(str, Enum):
    PROJECT_SETUP = "project_setup"
    BRIEF_UPLOAD = "brief_upload"
    BRIEF_REVIEW = "brief_review"
    METHODOLOGY_SELECTOR = "methodology_selector"
    SECTION_SELECTOR = "section_selector"
    QUESTIONNAIRE_EDITOR = "questionnaire_editor"
    QUESTIONNAIRE_VALIDATION = "questionnaire_validation"
    DATA_UPLOAD = "data_upload"
    MAPPING_EDITOR = "mapping_editor"
    TABLE_GENERATION = "table_generation"
    TABLE_QA = "table_qa"
    ANALYSIS_CONFIG = "analysis_config"
    ANALYSIS_RESULTS = "analysis_results"
    EXPORT = "export"


# ---------------------------------------------------------------------------
# Copilot panel — what the assistant does on each screen
# ---------------------------------------------------------------------------

class CopilotAction(str, Enum):
    SUGGEST = "suggest"          # Proactive recommendation
    EXPLAIN = "explain"          # Explain current state or result
    GENERATE = "generate"        # Create content (sections, mappings, etc.)
    VALIDATE = "validate"        # Check for issues
    FIX = "fix"                  # Propose targeted repair
    COMPARE = "compare"          # Diff versions or runs
    SUMMARIZE = "summarize"      # Condense results into narrative


class CopilotPanelSpec(BaseModel):
    """Defines copilot behavior for one screen."""

    screen: Screen
    workflow_stage: WorkflowStage
    context_chips: list[str] = Field(default_factory=list)
    available_actions: list[CopilotAction]
    default_action: CopilotAction
    proactive_triggers: list[str] = Field(default_factory=list)
    description: str


# ---------------------------------------------------------------------------
# Approval checkpoints — gates requiring explicit user confirmation
# ---------------------------------------------------------------------------

class CheckpointSeverity(str, Enum):
    BLOCKING = "blocking"      # Cannot proceed without approval
    WARNING = "warning"        # Can proceed but user should review


class ApprovalCheckpoint(BaseModel):
    """A gate requiring explicit user confirmation before proceeding."""

    checkpoint_id: str
    label: str
    screen: Screen
    severity: CheckpointSeverity
    description: str
    what_gets_locked: list[str]
    rollback_path: str
    requires_validation_pass: bool = False


# ---------------------------------------------------------------------------
# Fallback manual paths — what users can do without the assistant
# ---------------------------------------------------------------------------

class FallbackPath(BaseModel):
    """Manual alternative for each AI-assisted action."""

    screen: Screen
    ai_action: str
    manual_alternative: str
    manual_steps: list[str]


# ---------------------------------------------------------------------------
# Registry definitions
# ---------------------------------------------------------------------------

COPILOT_PANELS: dict[Screen, CopilotPanelSpec] = {
    Screen.PROJECT_SETUP: CopilotPanelSpec(
        screen=Screen.PROJECT_SETUP,
        workflow_stage=WorkflowStage.BRIEF,
        context_chips=["project_name"],
        available_actions=[CopilotAction.SUGGEST],
        default_action=CopilotAction.SUGGEST,
        proactive_triggers=["project_created"],
        description="Suggest methodology based on project name and category. Offer brief upload prompt.",
    ),
    Screen.BRIEF_UPLOAD: CopilotPanelSpec(
        screen=Screen.BRIEF_UPLOAD,
        workflow_stage=WorkflowStage.BRIEF,
        context_chips=["project_name", "methodology"],
        available_actions=[CopilotAction.SUGGEST, CopilotAction.EXPLAIN],
        default_action=CopilotAction.SUGGEST,
        proactive_triggers=["file_uploaded"],
        description="After upload, extract brief fields automatically. Highlight missing required fields.",
    ),
    Screen.BRIEF_REVIEW: CopilotPanelSpec(
        screen=Screen.BRIEF_REVIEW,
        workflow_stage=WorkflowStage.BRIEF,
        context_chips=["project_name", "methodology", "brief_status"],
        available_actions=[CopilotAction.SUMMARIZE, CopilotAction.SUGGEST, CopilotAction.EXPLAIN],
        default_action=CopilotAction.SUMMARIZE,
        proactive_triggers=["brief_parsed"],
        description="Summarize brief, identify gaps, propose assumptions for user confirmation.",
    ),
    Screen.METHODOLOGY_SELECTOR: CopilotPanelSpec(
        screen=Screen.METHODOLOGY_SELECTOR,
        workflow_stage=WorkflowStage.QUESTIONNAIRE,
        context_chips=["project_name", "methodology", "brief_summary"],
        available_actions=[CopilotAction.SUGGEST, CopilotAction.EXPLAIN],
        default_action=CopilotAction.SUGGEST,
        proactive_triggers=["brief_accepted"],
        description="Recommend methodology based on brief objectives. Explain trade-offs between options.",
    ),
    Screen.SECTION_SELECTOR: CopilotPanelSpec(
        screen=Screen.SECTION_SELECTOR,
        workflow_stage=WorkflowStage.QUESTIONNAIRE,
        context_chips=["project_name", "methodology", "brief_summary"],
        available_actions=[CopilotAction.SUGGEST, CopilotAction.EXPLAIN],
        default_action=CopilotAction.SUGGEST,
        proactive_triggers=["methodology_selected"],
        description="Pre-select recommended sections based on methodology and brief. Explain why each section matters.",
    ),
    Screen.QUESTIONNAIRE_EDITOR: CopilotPanelSpec(
        screen=Screen.QUESTIONNAIRE_EDITOR,
        workflow_stage=WorkflowStage.QUESTIONNAIRE,
        context_chips=["project_name", "methodology", "questionnaire_version", "active_section"],
        available_actions=[
            CopilotAction.GENERATE, CopilotAction.EXPLAIN, CopilotAction.FIX,
            CopilotAction.COMPARE, CopilotAction.VALIDATE,
        ],
        default_action=CopilotAction.GENERATE,
        proactive_triggers=["section_selected", "section_edited", "version_created"],
        description="Generate section content, explain design choices, fix validation issues, compare versions.",
    ),
    Screen.QUESTIONNAIRE_VALIDATION: CopilotPanelSpec(
        screen=Screen.QUESTIONNAIRE_VALIDATION,
        workflow_stage=WorkflowStage.QUESTIONNAIRE,
        context_chips=["project_name", "methodology", "questionnaire_version", "validation_status"],
        available_actions=[CopilotAction.VALIDATE, CopilotAction.FIX, CopilotAction.EXPLAIN],
        default_action=CopilotAction.VALIDATE,
        proactive_triggers=["validation_run_complete"],
        description="Show validation results, explain failures, propose targeted fixes with user approval.",
    ),
    Screen.DATA_UPLOAD: CopilotPanelSpec(
        screen=Screen.DATA_UPLOAD,
        workflow_stage=WorkflowStage.MAPPING,
        context_chips=["project_name", "methodology", "questionnaire_version"],
        available_actions=[CopilotAction.EXPLAIN, CopilotAction.SUGGEST],
        default_action=CopilotAction.EXPLAIN,
        proactive_triggers=["file_uploaded"],
        description="Profile uploaded data, show column summary, flag potential issues.",
    ),
    Screen.MAPPING_EDITOR: CopilotPanelSpec(
        screen=Screen.MAPPING_EDITOR,
        workflow_stage=WorkflowStage.MAPPING,
        context_chips=["project_name", "methodology", "questionnaire_version", "mapping_version", "data_file"],
        available_actions=[
            CopilotAction.GENERATE, CopilotAction.EXPLAIN, CopilotAction.FIX, CopilotAction.SUGGEST,
        ],
        default_action=CopilotAction.GENERATE,
        proactive_triggers=["data_profiled", "mapping_edited"],
        description="Auto-map columns to questionnaire variables, explain low-confidence mappings, apply user-approved fixes.",
    ),
    Screen.TABLE_GENERATION: CopilotPanelSpec(
        screen=Screen.TABLE_GENERATION,
        workflow_stage=WorkflowStage.TABLE_QA,
        context_chips=["project_name", "methodology", "questionnaire_version", "mapping_version"],
        available_actions=[CopilotAction.GENERATE, CopilotAction.EXPLAIN],
        default_action=CopilotAction.GENERATE,
        proactive_triggers=["mapping_locked"],
        description="Generate tables from locked mapping. Explain table structure and significance settings.",
    ),
    Screen.TABLE_QA: CopilotPanelSpec(
        screen=Screen.TABLE_QA,
        workflow_stage=WorkflowStage.TABLE_QA,
        context_chips=["project_name", "methodology", "run_id", "qa_status"],
        available_actions=[CopilotAction.VALIDATE, CopilotAction.EXPLAIN, CopilotAction.FIX],
        default_action=CopilotAction.VALIDATE,
        proactive_triggers=["tables_generated"],
        description="Run QA checks, explain findings, suggest corrective steps.",
    ),
    Screen.ANALYSIS_CONFIG: CopilotPanelSpec(
        screen=Screen.ANALYSIS_CONFIG,
        workflow_stage=WorkflowStage.ANALYSIS,
        context_chips=["project_name", "methodology", "questionnaire_version", "mapping_version"],
        available_actions=[CopilotAction.SUGGEST, CopilotAction.EXPLAIN],
        default_action=CopilotAction.SUGGEST,
        proactive_triggers=["tables_qa_passed"],
        description="Recommend analysis configuration based on methodology and data profile. Explain parameter choices.",
    ),
    Screen.ANALYSIS_RESULTS: CopilotPanelSpec(
        screen=Screen.ANALYSIS_RESULTS,
        workflow_stage=WorkflowStage.ANALYSIS,
        context_chips=["project_name", "methodology", "run_id", "analysis_type"],
        available_actions=[
            CopilotAction.EXPLAIN, CopilotAction.SUMMARIZE, CopilotAction.COMPARE,
        ],
        default_action=CopilotAction.SUMMARIZE,
        proactive_triggers=["analysis_complete"],
        description="Generate evidence-bound narrative, explain key findings, compare runs.",
    ),
    Screen.EXPORT: CopilotPanelSpec(
        screen=Screen.EXPORT,
        workflow_stage=WorkflowStage.REPORTING,
        context_chips=["project_name", "methodology", "questionnaire_version", "run_id"],
        available_actions=[CopilotAction.SUGGEST, CopilotAction.EXPLAIN],
        default_action=CopilotAction.SUGGEST,
        proactive_triggers=["export_requested"],
        description="Recommend export format, explain what is included, confirm provenance metadata.",
    ),
}


# ---------------------------------------------------------------------------
# Approval checkpoints
# ---------------------------------------------------------------------------

APPROVAL_CHECKPOINTS: list[ApprovalCheckpoint] = [
    ApprovalCheckpoint(
        checkpoint_id="publish_draft",
        label="Publish Questionnaire Draft",
        screen=Screen.QUESTIONNAIRE_EDITOR,
        severity=CheckpointSeverity.BLOCKING,
        description="Freezes the current questionnaire version as a publishable draft. "
                    "Subsequent edits create a new version.",
        what_gets_locked=["questionnaire_content", "section_order"],
        rollback_path="Create new version from published draft.",
        requires_validation_pass=True,
    ),
    ApprovalCheckpoint(
        checkpoint_id="lock_mapping",
        label="Lock Data Mapping",
        screen=Screen.MAPPING_EDITOR,
        severity=CheckpointSeverity.BLOCKING,
        description="Locks the column-to-variable mapping. Table generation and analysis "
                    "use the locked mapping version. Edits create a new mapping version.",
        what_gets_locked=["column_mappings", "variable_definitions", "scale_configs"],
        rollback_path="Create new mapping version and re-run downstream.",
    ),
    ApprovalCheckpoint(
        checkpoint_id="run_analysis",
        label="Launch Analysis Run",
        screen=Screen.ANALYSIS_CONFIG,
        severity=CheckpointSeverity.BLOCKING,
        description="Starts an analysis run with the current config. Run consumes compute "
                    "resources and produces artifacts that become part of project history.",
        what_gets_locked=["analysis_parameters", "input_versions"],
        rollback_path="Cancel queued run or start new run with different config.",
    ),
    ApprovalCheckpoint(
        checkpoint_id="export_artifacts",
        label="Export / Download Artifacts",
        screen=Screen.EXPORT,
        severity=CheckpointSeverity.WARNING,
        description="Generates export files (DOCX, Decipher, Excel). Exported artifacts are "
                    "stored with provenance but cannot be un-exported once shared externally.",
        what_gets_locked=["export_manifest", "provenance_record"],
        rollback_path="Re-export with updated version if needed.",
    ),
]


# ---------------------------------------------------------------------------
# Fallback manual paths
# ---------------------------------------------------------------------------

FALLBACK_PATHS: list[FallbackPath] = [
    FallbackPath(
        screen=Screen.PROJECT_SETUP,
        ai_action="AI suggests methodology based on project name and category",
        manual_alternative="Choose methodology manually during project setup",
        manual_steps=[
            "Enter project name and client details.",
            "Select methodology from the dropdown.",
            "Save project.",
        ],
    ),
    FallbackPath(
        screen=Screen.BRIEF_UPLOAD,
        ai_action="Auto-extract brief fields from uploaded document",
        manual_alternative="Manually fill brief fields",
        manual_steps=[
            "Click 'Manual Entry' tab on brief screen.",
            "Fill in: objectives, audience, category, geography, constraints.",
            "Save brief.",
        ],
    ),
    FallbackPath(
        screen=Screen.BRIEF_REVIEW,
        ai_action="AI summarizes brief and identifies gaps",
        manual_alternative="Review brief fields directly",
        manual_steps=[
            "Read extracted fields in the brief review panel.",
            "Edit any incorrect values inline.",
            "Mark brief as reviewed.",
        ],
    ),
    FallbackPath(
        screen=Screen.METHODOLOGY_SELECTOR,
        ai_action="AI recommends methodology based on brief",
        manual_alternative="Select methodology manually",
        manual_steps=[
            "Open methodology dropdown.",
            "Choose from available options.",
            "Confirm selection.",
        ],
    ),
    FallbackPath(
        screen=Screen.SECTION_SELECTOR,
        ai_action="AI pre-selects recommended sections",
        manual_alternative="Select sections manually",
        manual_steps=[
            "Review section checklist for chosen methodology.",
            "Check/uncheck desired sections.",
            "Required sections cannot be deselected.",
        ],
    ),
    FallbackPath(
        screen=Screen.QUESTIONNAIRE_EDITOR,
        ai_action="AI generates section content",
        manual_alternative="Write questions manually",
        manual_steps=[
            "Click 'Add Question' in the section editor.",
            "Enter question text, type, response options, and variable ID.",
            "Repeat for each question.",
            "Run validation when complete.",
        ],
    ),
    FallbackPath(
        screen=Screen.QUESTIONNAIRE_VALIDATION,
        ai_action="AI proposes fixes for validation failures",
        manual_alternative="Fix validation issues manually",
        manual_steps=[
            "Review validation report.",
            "Click on each failure to navigate to the question.",
            "Edit the question to resolve the issue.",
            "Re-run validation.",
        ],
    ),
    FallbackPath(
        screen=Screen.DATA_UPLOAD,
        ai_action="AI profiles uploaded data and flags issues",
        manual_alternative="Review data columns and types manually",
        manual_steps=[
            "Open uploaded file preview.",
            "Review column names, types, and row counts.",
            "Check for missing values or unexpected formats.",
            "Proceed to mapping when satisfied.",
        ],
    ),
    FallbackPath(
        screen=Screen.MAPPING_EDITOR,
        ai_action="AI auto-maps data columns to questionnaire variables",
        manual_alternative="Map columns manually",
        manual_steps=[
            "For each questionnaire variable, select the matching data column from dropdown.",
            "Set scale type, value labels, and coding.",
            "Save mapping.",
        ],
    ),
    FallbackPath(
        screen=Screen.TABLE_GENERATION,
        ai_action="AI generates tables from locked mapping",
        manual_alternative="Configure and trigger table generation manually",
        manual_steps=[
            "Select table types to generate (frequency, crosstab, mean, T2B).",
            "Choose banner variables and significance settings.",
            "Click 'Generate Tables'.",
            "Review output files in run folder.",
        ],
    ),
    FallbackPath(
        screen=Screen.TABLE_QA,
        ai_action="AI explains QA findings and suggests fixes",
        manual_alternative="Review QA report manually",
        manual_steps=[
            "Open QA report.",
            "Review each finding (base size, missing values, distributions).",
            "Decide whether to adjust mapping, filter data, or accept.",
        ],
    ),
    FallbackPath(
        screen=Screen.ANALYSIS_CONFIG,
        ai_action="AI recommends analysis parameters",
        manual_alternative="Configure analysis manually",
        manual_steps=[
            "Select analysis type (e.g., K-Means, Drivers, MaxDiff).",
            "Set parameters (cluster count, variables, DV selection).",
            "Review config summary.",
            "Launch run.",
        ],
    ),
    FallbackPath(
        screen=Screen.ANALYSIS_RESULTS,
        ai_action="AI generates evidence-bound narrative from results",
        manual_alternative="Read raw output tables",
        manual_steps=[
            "Open analysis output artifacts (Excel, CSV).",
            "Review tables, coefficients, and cluster profiles directly.",
            "Write findings narrative manually.",
        ],
    ),
    FallbackPath(
        screen=Screen.EXPORT,
        ai_action="AI recommends export format and contents",
        manual_alternative="Choose export options manually",
        manual_steps=[
            "Select export format (DOCX, Decipher, Excel).",
            "Select which artifacts to include.",
            "Click Export.",
        ],
    ),
]


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def get_copilot_spec(screen: Screen) -> CopilotPanelSpec:
    """Return copilot panel spec for a screen."""
    return COPILOT_PANELS[screen]


def get_checkpoints_for_screen(screen: Screen) -> list[ApprovalCheckpoint]:
    """Return approval checkpoints that apply to a screen."""
    return [cp for cp in APPROVAL_CHECKPOINTS if cp.screen == screen]


def get_fallback_for_screen(screen: Screen) -> list[FallbackPath]:
    """Return fallback manual paths for a screen."""
    return [fp for fp in FALLBACK_PATHS if fp.screen == screen]


def get_all_screens_summary() -> list[dict[str, Any]]:
    """Return a summary of all screens with copilot, checkpoints, and fallbacks."""
    result = []
    for screen in Screen:
        panel = COPILOT_PANELS.get(screen)
        result.append({
            "screen": screen.value,
            "workflow_stage": panel.workflow_stage.value if panel else None,
            "copilot_actions": [a.value for a in panel.available_actions] if panel else [],
            "has_checkpoint": any(cp.screen == screen for cp in APPROVAL_CHECKPOINTS),
            "has_fallback": any(fp.screen == screen for fp in FALLBACK_PATHS),
        })
    return result
