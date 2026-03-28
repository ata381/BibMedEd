import axios from 'axios';

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
});

// Types
export interface Project {
  id: number;
  name: string;
  description: string | null;
  date_range_start: string | null;
  date_range_end: string | null;
  created_at: string;
  updated_at: string;
}

export interface Publication {
  id: number;
  pmid: string;
  doi: string | null;
  title: string;
  abstract: string | null;
  year: number | null;
  publication_type: string | null;
  citation_count: number | null;
  excluded: boolean;
  journal_name: string | null;
  authors: { id: number; name: string; orcid: string | null }[];
}

export interface SearchStatus {
  query_id: number;
  status: string;
  result_count: number | null;
  raw_result_count: number | null;
  duplicate_count: number | null;
  progress: number | null;
}

export interface AnalysisResult {
  id: number;
  project_id: number;
  analysis_type: string;
  results: any;
  created_at: string;
}

// API functions
export const projectsApi = {
  list: () => api.get<Project[]>('/api/projects'),
  get: (id: number) => api.get<Project>(`/api/projects/${id}`),
  create: (data: { name: string; description?: string; date_range_start?: string; date_range_end?: string }) =>
    api.post<Project>('/api/projects', data),
  delete: (id: number) => api.delete(`/api/projects/${id}`),
};

export const searchApi = {
  trigger: (projectId: number, queryString: string) =>
    api.post<SearchStatus>(`/api/projects/${projectId}/search`, { query_string: queryString }),
  status: (projectId: number, queryId: number) =>
    api.get<SearchStatus>(`/api/projects/${projectId}/search/${queryId}`),
  latest: (projectId: number) =>
    api.get<SearchStatus>(`/api/projects/${projectId}/search/latest`),
};

export const publicationsApi = {
  list: (projectId: number, params?: { sort_by?: string; order?: string; limit?: number; offset?: number }) =>
    api.get<{ total: number; items: Publication[] }>(`/api/projects/${projectId}/publications`, { params }),
  toggleExclude: (projectId: number, publicationId: number) =>
    api.patch<{ id: number; excluded: boolean }>(`/api/projects/${projectId}/publications/${publicationId}/exclude`),
  bulkExclude: (projectId: number, citationThreshold: number) =>
    api.post<{ excluded_count: number }>(`/api/projects/${projectId}/publications/bulk-exclude`, { citation_threshold: citationThreshold }),
};

export const analysisApi = {
  run: (projectId: number, type: string) =>
    api.post<AnalysisResult>(`/api/projects/${projectId}/analysis/${type}`),
  get: (projectId: number, type: string) =>
    api.get<AnalysisResult>(`/api/projects/${projectId}/analysis/${type}`),
};

export const exportApi = {
  csvUrl: (projectId: number) =>
    `${api.defaults.baseURL}/api/projects/${projectId}/export/csv`,
  risUrl: (projectId: number) =>
    `${api.defaults.baseURL}/api/projects/${projectId}/export/ris`,
};

export default api;
