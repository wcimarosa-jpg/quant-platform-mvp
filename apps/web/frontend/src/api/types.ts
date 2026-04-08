/**
 * Typed response interfaces for API endpoints.
 * Keep in sync with backend Pydantic models.
 */

// -- Projects --
export interface Project {
  id: string;
  name: string;
  methodology: string;
  status: string;
}

export interface ProjectListResponse {
  projects: Project[];
  total: number;
}

// -- Briefs --
//
// Note: `Brief` (returned by GET /briefs/:id) intentionally has `project_id`
// optional because the backend get_brief endpoint does not return it. The
// upload response (BriefUploadResponse below) does include project_id since
// the client just supplied it. This asymmetry is documented here so future
// devs don't try to "fix" the optional flag by reading it from getBrief.
export interface Brief {
  brief_id: string;
  project_id?: string;
  source_filename?: string;
  source_format?: string;
  objectives: string | null;
  audience: string | null;
  category: string | null;
  geography: string | null;
  constraints: string | null;
  raw_text?: string;
  raw_text_truncated?: boolean;
  missing_fields: string[];
  is_complete: boolean;
}

export interface BriefUploadResponse {
  brief_id: string;
  project_id: string;
  source_filename: string;
  source_format: string;
  extracted_fields: {
    objectives: string | null;
    audience: string | null;
    category: string | null;
    geography: string | null;
    constraints: string | null;
  };
  missing_fields: string[];
  is_complete: boolean;
}

export interface Assumption {
  assumption_id: string;
  field: string;
  proposal: string;
  rationale: string;
  source_reference: string | null;
  status: string;
}

export interface BriefAnalysis {
  analysis_id: string;
  brief_id: string;
  summary: string;
  gaps: string[];
  assumptions: Assumption[];
  all_resolved: boolean;
}

// -- Drafts --
export interface DraftSection {
  section_type: string;
  label: string;
  required: boolean;
  selected: boolean;
}

export interface Draft {
  draft_id: string;
  project_id: string;
  methodology: string;
  selected_sections: string[];
  section_options: DraftSection[];
  updated_at: string;
}

export interface Methodology {
  value: string;
  label: string;
  description: string;
}

// -- Tables / Analysis --
export interface TableRunResponse {
  run_id: string;
  total_tables: number;
  provenance: Record<string, unknown>;
}

export interface QAFinding {
  finding_id: string;
  table_id: string;
  severity: string;
  message: string;
}

export interface QAReport {
  report_id: string;
  run_id: string;
  passed: boolean;
  error_count: number;
  warning_count: number;
  findings: QAFinding[];
}

export interface QACopilotExplanation {
  finding_id: string;
  explanation: string;
}

export interface QACopilotAction {
  action_id: string;
  finding_id: string;
  action_type: string;
  description: string;
  status: string;
}

export interface QACopilotSession {
  session_id: string;
  report_id: string;
  explanations: QACopilotExplanation[];
  actions: QACopilotAction[];
  all_resolved: boolean;
}

// -- Cost --
export interface CostResponse {
  total_tokens: number;
  total_cost_usd: number;
  by_stage?: Record<string, number>;
  by_project?: Record<string, number>;
  by_run?: Record<string, number>;
}
