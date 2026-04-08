/**
 * API client for the quant platform backend.
 * All calls target the FastAPI server at the configured base URL.
 */

import type {
  Brief,
  BriefAnalysis,
  BriefUploadResponse,
  CostResponse,
  Draft,
  Methodology,
  Project,
  ProjectListResponse,
  QACopilotSession,
  QAReport,
  TableRunResponse,
} from './types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8010';

interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
}

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

// Single-flight 401 redirect guard — multiple parallel requests on first
// page load can each trigger a redirect, causing duplicate history entries.
let _redirecting = false;

function _handle401() {
  if (_redirecting) return;
  _redirecting = true;
  localStorage.removeItem('quant_token');
  localStorage.removeItem('quant_user');
  if (window.location.pathname !== '/login') {
    window.location.replace('/login');
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, headers = {} } = options;
  const url = `${API_BASE}${path}`;

  const fetchHeaders: Record<string, string> = { ...headers };

  // Attach auth token if available
  const token = localStorage.getItem('quant_token');
  if (token) {
    fetchHeaders['Authorization'] = `Bearer ${token}`;
  }

  const fetchOptions: RequestInit = { method };

  if (body instanceof FormData) {
    // Let browser set Content-Type with multipart boundary
    fetchOptions.body = body;
  } else if (body) {
    fetchHeaders['Content-Type'] = 'application/json';
    fetchOptions.body = JSON.stringify(body);
  }
  fetchOptions.headers = fetchHeaders;

  const response = await fetch(url, fetchOptions);
  if (response.status === 401) {
    _handle401();
    throw new ApiError(401, 'Authentication required');
  }
  if (!response.ok) {
    let detail = 'Unknown error';
    try {
      const text = await response.text();
      // Try to parse JSON {"detail": "..."} from FastAPI
      try {
        const parsed = JSON.parse(text);
        detail = parsed.detail || text;
      } catch {
        detail = text;
      }
    } catch {
      // ignore — use default
    }
    throw new ApiError(response.status, detail);
  }

  // Handle empty bodies (204 No Content, or empty 200)
  if (response.status === 204) {
    return undefined as T;
  }
  const contentLength = response.headers.get('content-length');
  if (contentLength === '0') {
    return undefined as T;
  }
  // Parse JSON body, but tolerate empty body responses
  const text = await response.text();
  if (!text) {
    return undefined as T;
  }
  return JSON.parse(text) as T;
}

// Re-export types for convenience
export type {
  Brief,
  BriefAnalysis,
  BriefUploadResponse,
  CostResponse,
  Draft,
  Methodology,
  Project,
  ProjectListResponse,
  QACopilotSession,
  QAReport,
  TableRunResponse,
};

interface CreateProjectRequest {
  name: string;
  methodology: string;
}

interface BriefUpdateRequest {
  objectives?: string;
  audience?: string;
  category?: string;
  geography?: string;
  constraints?: string;
}

interface CreateDraftRequest {
  project_id: string;
  methodology: string;
}

interface UpdateSectionsRequest {
  selected_sections: string[];
}

export const api = {
  // Health
  health: () => request<{ ok: boolean; version: string }>('/health'),
  healthDetailed: () => request<Record<string, unknown>>('/health/detailed'),

  // Projects
  listProjects: () => request<ProjectListResponse>('/api/v1/projects/'),
  createProject: (data: CreateProjectRequest) =>
    request<Project>('/api/v1/projects/', { method: 'POST', body: data }),

  // Briefs
  uploadBrief: (projectId: string, file: File): Promise<BriefUploadResponse> => {
    const fd = new FormData();
    fd.append('file', file);
    return request<BriefUploadResponse>(
      `/api/v1/briefs/upload?project_id=${encodeURIComponent(projectId)}`,
      { method: 'POST', body: fd },
    );
  },
  getBrief: (id: string) => request<Brief>(`/api/v1/briefs/${id}`),
  updateBrief: (id: string, data: BriefUpdateRequest) =>
    request<Brief>(`/api/v1/briefs/${id}`, { method: 'PATCH', body: data }),
  analyzeBrief: (briefId: string) =>
    request<BriefAnalysis>(`/api/v1/briefs/${briefId}/analyze`, { method: 'POST' }),

  // Drafts / Survey
  listMethodologies: () => request<{ methodologies: Methodology[] }>('/api/v1/drafts/methodologies'),
  createDraft: (data: CreateDraftRequest) =>
    request<Draft>('/api/v1/drafts/', { method: 'POST', body: data }),
  getDraft: (id: string) => request<Draft>(`/api/v1/drafts/${id}`),
  updateSections: (id: string, data: UpdateSectionsRequest) =>
    request<Draft>(`/api/v1/drafts/${id}/sections`, { method: 'PATCH', body: data }),

  // Tables / Analysis
  generateTables: (data: Record<string, unknown>) =>
    request<TableRunResponse>('/api/v1/tables/generate', { method: 'POST', body: data }),
  runQA: (runId: string) =>
    request<QAReport>(`/api/v1/tables/${runId}/qa`, { method: 'POST' }),
  runQACopilot: (runId: string) =>
    request<QACopilotSession>(`/api/v1/tables/${runId}/qa-copilot`, { method: 'POST' }),

  // Ops
  getMetrics: () => request<Record<string, unknown>>('/ops/metrics'),
  getSLOs: () => request<Record<string, unknown>>('/ops/slos'),
  getCost: () => request<CostResponse>('/ops/cost'),
  getAlerts: () => request<Record<string, unknown>>('/ops/alerts'),
};

export { ApiError };
export default api;
