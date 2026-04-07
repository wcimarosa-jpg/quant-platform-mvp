/**
 * API client for the quant platform backend.
 * All calls target the FastAPI server at the configured base URL.
 */

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
  if (!response.ok) {
    const text = await response.text().catch(() => 'Unknown error');
    throw new ApiError(response.status, text);
  }
  return response.json();
}

// -- Projects --
export const api = {
  // Health
  health: () => request<{ ok: boolean; version: string }>('/health'),
  healthDetailed: () => request<Record<string, unknown>>('/health/detailed'),

  // Projects
  listProjects: () => request<Record<string, unknown>[]>('/api/v1/projects'),
  createProject: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>('/api/v1/projects', { method: 'POST', body: data }),

  // Briefs
  getBrief: (id: string) => request<Record<string, unknown>>(`/api/v1/briefs/${id}`),
  updateBrief: (id: string, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/api/v1/briefs/${id}`, { method: 'PATCH', body: data }),
  analyzeBrief: (briefId: string) =>
    request<Record<string, unknown>>(`/api/v1/briefs/${briefId}/analyze`, { method: 'POST' }),

  // Drafts / Survey
  listMethodologies: () => request<Record<string, unknown>[]>('/api/v1/drafts/methodologies'),
  getDraft: (id: string) => request<Record<string, unknown>>(`/api/v1/drafts/${id}`),
  updateSections: (id: string, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/api/v1/drafts/${id}/sections`, { method: 'PATCH', body: data }),

  // Tables / Analysis
  generateTables: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>('/api/v1/tables/generate', { method: 'POST', body: data }),
  runQA: (runId: string) =>
    request<Record<string, unknown>>(`/api/v1/tables/${runId}/qa`, { method: 'POST' }),

  // Assistant
  getPanelState: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>('/api/v1/assistant/panel-state', { method: 'POST', body: data }),

  // Ops
  getMetrics: () => request<Record<string, unknown>>('/ops/metrics'),
  getSLOs: () => request<Record<string, unknown>>('/ops/slos'),
  getCost: () => request<Record<string, unknown>>('/ops/cost'),
  getAlerts: () => request<Record<string, unknown>>('/ops/alerts'),
};

export { ApiError };
export default api;
