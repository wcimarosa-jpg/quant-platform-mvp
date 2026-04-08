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
    // Token expired or missing — clear auth and redirect to login
    localStorage.removeItem('quant_token');
    localStorage.removeItem('quant_user');
    if (window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
    throw new ApiError(401, 'Authentication required');
  }
  if (!response.ok) {
    const text = await response.text().catch(() => 'Unknown error');
    throw new ApiError(response.status, text);
  }
  return response.json();
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
    request<Record<string, unknown>>(`/api/v1/tables/${runId}/qa-copilot`, { method: 'POST' }),

  // Ops
  getMetrics: () => request<Record<string, unknown>>('/ops/metrics'),
  getSLOs: () => request<Record<string, unknown>>('/ops/slos'),
  getCost: () => request<CostResponse>('/ops/cost'),
  getAlerts: () => request<Record<string, unknown>>('/ops/alerts'),
};

export { ApiError };
export default api;
