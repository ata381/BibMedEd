import axios from 'axios';

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
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

export interface ProjectUpdateInput {
  name?: string;
  description?: string | null;
  date_range_start?: string | null;
  date_range_end?: string | null;
}

export type ExclusionReason =
  | "wrong_study_design"
  | "wrong_population"
  | "wrong_intervention"
  | "wrong_outcome"
  | "not_peer_reviewed"
  | "non_english"
  | "duplicate"
  | "fulltext_unavailable"
  | "other";

export const EXCLUSION_REASON_LABELS: Record<ExclusionReason, string> = {
  wrong_study_design: "Wrong study design",
  wrong_population: "Wrong population",
  wrong_intervention: "Wrong intervention",
  wrong_outcome: "Wrong outcome",
  not_peer_reviewed: "Not peer-reviewed (abstract / preprint / editorial)",
  non_english: "Non-English language",
  duplicate: "Duplicate (missed by automated dedup)",
  fulltext_unavailable: "Full-text not retrievable",
  other: "Other / unspecified",
};

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
  exclusion_reason: ExclusionReason | null;
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
  results: Record<string, unknown>;
  created_at: string;
}

export interface AdapterInfo {
  name: string;
  display_name: string;
  requires_api_key: boolean;
}

// API functions
export const projectsApi = {
  list: () => api.get<Project[]>('/api/projects'),
  get: (id: number) => api.get<Project>(`/api/projects/${id}`),
  create: (data: { name: string; description?: string; date_range_start?: string; date_range_end?: string }) =>
    api.post<Project>('/api/projects', data),
  createSample: () =>
    api.post<Project>('/api/projects/sample'),
  update: (id: number, data: ProjectUpdateInput) =>
    api.patch<Project>(`/api/projects/${id}`, data),
  delete: (id: number) => api.delete(`/api/projects/${id}`),
};

export const searchApi = {
  trigger: (projectId: number, queryString: string, source: string = "pubmed", yearStart?: string, yearEnd?: string, maxResults: number = 2000) =>
    api.post<SearchStatus>(`/api/projects/${projectId}/search`, { query_string: queryString, source, year_start: yearStart, year_end: yearEnd, max_results: maxResults }),
  status: (projectId: number, queryId: number) =>
    api.get<SearchStatus>(`/api/projects/${projectId}/search/${queryId}`),
  latest: (projectId: number) =>
    api.get<SearchStatus>(`/api/projects/${projectId}/search/latest`),
};

export const publicationsApi = {
  list: (projectId: number, params?: { sort_by?: string; order?: string; limit?: number; offset?: number }) =>
    api.get<{ total: number; excluded_count: number; items: Publication[] }>(`/api/projects/${projectId}/publications`, { params }),
  toggleExclude: (projectId: number, publicationId: number, reason?: ExclusionReason) =>
    api.patch<{ id: number; excluded: boolean; exclusion_reason: ExclusionReason | null }>(
      `/api/projects/${projectId}/publications/${publicationId}/exclude`,
      reason ? { reason } : {},
    ),
  bulkExclude: (projectId: number, citationThreshold: number, reason: ExclusionReason = "other") =>
    api.post<{ excluded_count: number; reason: ExclusionReason }>(
      `/api/projects/${projectId}/publications/bulk-exclude`,
      { citation_threshold: citationThreshold, reason },
    ),
};

export const analysisApi = {
  run: (projectId: number, type: string) =>
    api.post<AnalysisResult>(`/api/projects/${projectId}/analysis/${type}`),
  get: (projectId: number, type: string) =>
    api.get<AnalysisResult>(`/api/projects/${projectId}/analysis/${type}`),
};

export const adaptersApi = {
  list: () => api.get<AdapterInfo[]>('/api/adapters'),
};

export const exportApi = {
  csvUrl: (projectId: number) =>
    `${API_BASE_URL}/api/projects/${projectId}/export/csv`,
  risUrl: (projectId: number) =>
    `${API_BASE_URL}/api/projects/${projectId}/export/ris`,
  jsonUrl: (projectId: number) =>
    `${API_BASE_URL}/api/projects/${projectId}/export/json`,
  methodologyUrl: (projectId: number) =>
    `${API_BASE_URL}/api/projects/${projectId}/export/methodology`,
  prismaUrl: (projectId: number) =>
    `${API_BASE_URL}/api/projects/${projectId}/export/prisma`,
  bundleUrl: (projectId: number) =>
    `${API_BASE_URL}/api/projects/${projectId}/export/bundle`,
};

export default api;
