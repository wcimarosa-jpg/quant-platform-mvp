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
    """Manual alternative for a specific AI-assisted action on a screen."""

    screen: Screen
    ai_action_type: CopilotAction       # typed action this fallback covers
    ai_action: str                       # human-readable description
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
    # --- PROJECT_SETUP: suggest ---
    FallbackPath(screen=Screen.PROJECT_SETUP, ai_action_type=CopilotAction.SUGGEST,
                 ai_action="AI suggests methodology based on project name and category",
                 manual_alternative="Choose methodology manually",
                 manual_steps=["Enter project name.", "Select methodology from dropdown.", "Save project."]),
    # --- BRIEF_UPLOAD: suggest, explain ---
    FallbackPath(screen=Screen.BRIEF_UPLOAD, ai_action_type=CopilotAction.SUGGEST,
                 ai_action="AI suggests missing brief fields after upload",
                 manual_alternative="Fill brief fields manually",
                 manual_steps=["Click 'Manual Entry' tab.", "Fill in objectives, audience, category, geography, constraints.", "Save."]),
    FallbackPath(screen=Screen.BRIEF_UPLOAD, ai_action_type=CopilotAction.EXPLAIN,
                 ai_action="AI explains extracted brief structure",
                 manual_alternative="Read extracted fields directly",
                 manual_steps=["Review the parsed brief fields in the form.", "Edit any incorrect values."]),
    # --- BRIEF_REVIEW: summarize, suggest, explain ---
    FallbackPath(screen=Screen.BRIEF_REVIEW, ai_action_type=CopilotAction.SUMMARIZE,
                 ai_action="AI summarizes brief and identifies gaps",
                 manual_alternative="Read brief fields directly",
                 manual_steps=["Read extracted fields in brief review panel.", "Check for missing values."]),
    FallbackPath(screen=Screen.BRIEF_REVIEW, ai_action_type=CopilotAction.SUGGEST,
                 ai_action="AI suggests assumptions for missing fields",
                 manual_alternative="Enter missing values manually",
                 manual_steps=["Identify missing fields.", "Type values directly.", "Save."]),
    FallbackPath(screen=Screen.BRIEF_REVIEW, ai_action_type=CopilotAction.EXPLAIN,
                 ai_action="AI explains brief interpretation",
                 manual_alternative="Review raw brief text",
                 manual_steps=["Open raw brief text panel.", "Compare with extracted fields."]),
    # --- METHODOLOGY_SELECTOR: suggest, explain ---
    FallbackPath(screen=Screen.METHODOLOGY_SELECTOR, ai_action_type=CopilotAction.SUGGEST,
                 ai_action="AI recommends methodology",
                 manual_alternative="Select methodology manually",
                 manual_steps=["Open methodology dropdown.", "Choose option.", "Confirm."]),
    FallbackPath(screen=Screen.METHODOLOGY_SELECTOR, ai_action_type=CopilotAction.EXPLAIN,
                 ai_action="AI explains methodology trade-offs",
                 manual_alternative="Read methodology descriptions",
                 manual_steps=["Hover over each methodology for tooltip.", "Review documentation."]),
    # --- SECTION_SELECTOR: suggest, explain ---
    FallbackPath(screen=Screen.SECTION_SELECTOR, ai_action_type=CopilotAction.SUGGEST,
                 ai_action="AI pre-selects recommended sections",
                 manual_alternative="Select sections manually",
                 manual_steps=["Review section checklist.", "Check/uncheck sections.", "Required sections stay checked."]),
    FallbackPath(screen=Screen.SECTION_SELECTOR, ai_action_type=CopilotAction.EXPLAIN,
                 ai_action="AI explains why each section matters",
                 manual_alternative="Read section descriptions",
                 manual_steps=["Click section label for description.", "Review typical question counts."]),
    # --- QUESTIONNAIRE_EDITOR: generate, explain, fix, compare, validate ---
    FallbackPath(screen=Screen.QUESTIONNAIRE_EDITOR, ai_action_type=CopilotAction.GENERATE,
                 ai_action="AI generates section content",
                 manual_alternative="Write questions manually",
                 manual_steps=["Click 'Add Question'.", "Enter question text, type, options, variable ID.", "Repeat."]),
    FallbackPath(screen=Screen.QUESTIONNAIRE_EDITOR, ai_action_type=CopilotAction.EXPLAIN,
                 ai_action="AI explains design choices",
                 manual_alternative="Read question annotations",
                 manual_steps=["Review question metadata and logic notes."]),
    FallbackPath(screen=Screen.QUESTIONNAIRE_EDITOR, ai_action_type=CopilotAction.FIX,
                 ai_action="AI proposes fixes for issues",
                 manual_alternative="Edit questions directly",
                 manual_steps=["Navigate to flagged question.", "Edit text/options/logic.", "Re-validate."]),
    FallbackPath(screen=Screen.QUESTIONNAIRE_EDITOR, ai_action_type=CopilotAction.COMPARE,
                 ai_action="AI compares questionnaire versions",
                 manual_alternative="Use version diff view",
                 manual_steps=["Select two versions.", "Review side-by-side diff."]),
    FallbackPath(screen=Screen.QUESTIONNAIRE_EDITOR, ai_action_type=CopilotAction.VALIDATE,
                 ai_action="AI validates questionnaire",
                 manual_alternative="Run validation manually",
                 manual_steps=["Click 'Validate'.", "Review report."]),
    # --- QUESTIONNAIRE_VALIDATION: validate, fix, explain ---
    FallbackPath(screen=Screen.QUESTIONNAIRE_VALIDATION, ai_action_type=CopilotAction.VALIDATE,
                 ai_action="AI runs validation checks",
                 manual_alternative="Run validation manually",
                 manual_steps=["Click 'Run Validation'.", "Review error list."]),
    FallbackPath(screen=Screen.QUESTIONNAIRE_VALIDATION, ai_action_type=CopilotAction.FIX,
                 ai_action="AI proposes targeted fixes",
                 manual_alternative="Fix issues manually",
                 manual_steps=["Click each failure.", "Edit the question.", "Re-run validation."]),
    FallbackPath(screen=Screen.QUESTIONNAIRE_VALIDATION, ai_action_type=CopilotAction.EXPLAIN,
                 ai_action="AI explains validation failures",
                 manual_alternative="Read error descriptions",
                 manual_steps=["Click error for details.", "Review suggestion text."]),
    # --- DATA_UPLOAD: explain, suggest ---
    FallbackPath(screen=Screen.DATA_UPLOAD, ai_action_type=CopilotAction.EXPLAIN,
                 ai_action="AI profiles data and explains structure",
                 manual_alternative="Review data preview manually",
                 manual_steps=["Open file preview.", "Review column names and types.", "Check row counts."]),
    FallbackPath(screen=Screen.DATA_UPLOAD, ai_action_type=CopilotAction.SUGGEST,
                 ai_action="AI flags potential data issues",
                 manual_alternative="Check data quality manually",
                 manual_steps=["Review missingness summary.", "Check for unexpected formats."]),
    # --- MAPPING_EDITOR: generate, explain, fix, suggest ---
    FallbackPath(screen=Screen.MAPPING_EDITOR, ai_action_type=CopilotAction.GENERATE,
                 ai_action="AI auto-maps columns to variables",
                 manual_alternative="Map columns manually",
                 manual_steps=["For each variable, select matching column from dropdown.", "Save mapping."]),
    FallbackPath(screen=Screen.MAPPING_EDITOR, ai_action_type=CopilotAction.EXPLAIN,
                 ai_action="AI explains low-confidence mappings",
                 manual_alternative="Review mapping confidence scores",
                 manual_steps=["Check confidence column.", "Review match reason."]),
    FallbackPath(screen=Screen.MAPPING_EDITOR, ai_action_type=CopilotAction.FIX,
                 ai_action="AI suggests mapping corrections",
                 manual_alternative="Edit mappings directly",
                 manual_steps=["Click on low-confidence mapping.", "Select correct column.", "Save."]),
    FallbackPath(screen=Screen.MAPPING_EDITOR, ai_action_type=CopilotAction.SUGGEST,
                 ai_action="AI suggests unmapped variable assignments",
                 manual_alternative="Assign unmapped variables manually",
                 manual_steps=["Review unmapped list.", "Assign columns.", "Save."]),
    # --- TABLE_GENERATION: generate, explain ---
    FallbackPath(screen=Screen.TABLE_GENERATION, ai_action_type=CopilotAction.GENERATE,
                 ai_action="AI generates tables from locked mapping",
                 manual_alternative="Configure and trigger generation manually",
                 manual_steps=["Select table types.", "Choose banner variables.", "Click 'Generate Tables'."]),
    FallbackPath(screen=Screen.TABLE_GENERATION, ai_action_type=CopilotAction.EXPLAIN,
                 ai_action="AI explains table structure",
                 manual_alternative="Review table configuration",
                 manual_steps=["Review table type descriptions.", "Check significance settings."]),
    # --- TABLE_QA: validate, explain, fix ---
    FallbackPath(screen=Screen.TABLE_QA, ai_action_type=CopilotAction.VALIDATE,
                 ai_action="AI runs QA checks on tables",
                 manual_alternative="Review QA report manually",
                 manual_steps=["Open QA report.", "Review each finding."]),
    FallbackPath(screen=Screen.TABLE_QA, ai_action_type=CopilotAction.EXPLAIN,
                 ai_action="AI explains QA findings",
                 manual_alternative="Read finding descriptions",
                 manual_steps=["Click each finding for details.", "Review remediation hints."]),
    FallbackPath(screen=Screen.TABLE_QA, ai_action_type=CopilotAction.FIX,
                 ai_action="AI suggests QA fixes",
                 manual_alternative="Fix issues manually",
                 manual_steps=["Review suggested actions.", "Decide: suppress, merge, or accept."]),
    # --- ANALYSIS_CONFIG: suggest, explain ---
    FallbackPath(screen=Screen.ANALYSIS_CONFIG, ai_action_type=CopilotAction.SUGGEST,
                 ai_action="AI recommends analysis parameters",
                 manual_alternative="Configure analysis manually",
                 manual_steps=["Select analysis type.", "Set parameters.", "Review config.", "Launch."]),
    FallbackPath(screen=Screen.ANALYSIS_CONFIG, ai_action_type=CopilotAction.EXPLAIN,
                 ai_action="AI explains parameter choices",
                 manual_alternative="Read parameter descriptions",
                 manual_steps=["Hover over each parameter for tooltip.", "Review methodology guide."]),
    # --- ANALYSIS_RESULTS: explain, summarize, compare ---
    FallbackPath(screen=Screen.ANALYSIS_RESULTS, ai_action_type=CopilotAction.EXPLAIN,
                 ai_action="AI explains analysis results",
                 manual_alternative="Read raw output tables",
                 manual_steps=["Open output artifacts.", "Review tables and coefficients."]),
    FallbackPath(screen=Screen.ANALYSIS_RESULTS, ai_action_type=CopilotAction.SUMMARIZE,
                 ai_action="AI generates evidence-bound narrative",
                 manual_alternative="Write findings manually",
                 manual_steps=["Review output tables.", "Draft narrative in document editor."]),
    FallbackPath(screen=Screen.ANALYSIS_RESULTS, ai_action_type=CopilotAction.COMPARE,
                 ai_action="AI compares analysis runs",
                 manual_alternative="Use run comparison view",
                 manual_steps=["Select two runs.", "Review metric deltas."]),
    # --- EXPORT: suggest, explain ---
    FallbackPath(screen=Screen.EXPORT, ai_action_type=CopilotAction.SUGGEST,
                 ai_action="AI recommends export format",
                 manual_alternative="Choose export options manually",
                 manual_steps=["Select format.", "Select artifacts.", "Click Export."]),
    FallbackPath(screen=Screen.EXPORT, ai_action_type=CopilotAction.EXPLAIN,
                 ai_action="AI explains what is included in export",
                 manual_alternative="Review export contents list",
                 manual_steps=["Review artifact list.", "Check provenance metadata."]),
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


def check_fallback_action_coverage() -> dict[str, Any]:
    """Check that every (screen, action) pair from COPILOT_PANELS has a fallback.

    Returns {"covered": [...], "missing": [...], "total_pairs": N, "covered_count": N}.
    """
    covered: list[tuple[str, str]] = []
    missing: list[tuple[str, str]] = []

    for screen, spec in COPILOT_PANELS.items():
        fallback_actions = {fp.ai_action_type for fp in FALLBACK_PATHS if fp.screen == screen}
        for action in spec.available_actions:
            pair = (screen.value, action.value)
            if action in fallback_actions:
                covered.append(pair)
            else:
                missing.append(pair)

    return {
        "covered": covered,
        "missing": missing,
        "total_pairs": len(covered) + len(missing),
        "covered_count": len(covered),
    }


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
