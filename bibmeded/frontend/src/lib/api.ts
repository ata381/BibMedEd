import axios from 'axios';

const demoPath = process.env.NEXT_PUBLIC_PAGES_DEMO_PATH;
export const isPagesDemo = Boolean(demoPath);
const apiBaseUrl = demoPath ? `${demoPath}/demo-data` : (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000');

const api = axios.create({
  baseURL: apiBaseUrl,
});

if (isPagesDemo) {
  api.interceptors.request.use((config) => {
    if (config.method !== "get") throw new Error("The sample project is read-only.");
    config.url = `${config.url}.json`;
    return config;
  });
}

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

export type ScreeningStage = "title_abstract" | "full_text";

export const SCREENING_STAGE_LABELS: Record<ScreeningStage, string> = {
  title_abstract: "Title / abstract",
  full_text: "Full text",
};

// PRISMA 2020 reports this reason as "Reports not retrieved", which exists only
// at the full-text stage; the API rejects it at title/abstract.
export const NOT_RETRIEVED_REASON: ExclusionReason = "fulltext_unavailable";

export function stageForReason(reason: ExclusionReason, selected: ScreeningStage): ScreeningStage {
  return reason === NOT_RETRIEVED_REASON ? "full_text" : selected;
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
  exclusion_reason: ExclusionReason | null;
  screening_stage: ScreeningStage | null;
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
  query_string?: string | null;
  database?: string | null;
}

export interface AnalysisResult {
  stale: boolean;
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
    api.get<{ total: number; excluded_count: number; zero_citation_count: number; missing_citation_count: number; items: Publication[] }>(`/api/projects/${projectId}/publications`, { params }),
  toggleExclude: (projectId: number, publicationId: number, reason?: ExclusionReason, screeningStage?: ScreeningStage) =>
    api.patch<{
      id: number;
      excluded: boolean;
      exclusion_reason: ExclusionReason | null;
      screening_stage: ScreeningStage | null;
    }>(
      `/api/projects/${projectId}/publications/${publicationId}/exclude`,
      {
        ...(reason ? { reason } : {}),
        ...(screeningStage ? { screening_stage: screeningStage } : {}),
      },
    ),
  bulkExclude: (projectId: number, citationThreshold: number, reason: ExclusionReason = "other") =>
    api.post<{ excluded_count: number; reason: ExclusionReason; screening_stage: ScreeningStage }>(
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

const exportUrl = (projectId: number, route: string, filename: string) =>
  `${apiBaseUrl}/api/projects/${projectId}/export/${isPagesDemo ? filename : route}`;

export const exportApi = {
  csvUrl: (projectId: number) => exportUrl(projectId, "csv", "sample.csv"),
  risUrl: (projectId: number) => exportUrl(projectId, "ris", "sample.ris"),
  wosUrl: (projectId: number) => exportUrl(projectId, "wos", "sample-wos.txt"),
  bibtexUrl: (projectId: number) => exportUrl(projectId, "bibtex", "sample.bib"),
  jsonUrl: (projectId: number) => exportUrl(projectId, "json", "sample.json"),
  methodologyUrl: (projectId: number) => exportUrl(projectId, "methodology", "sample-methodology.txt"),
  prismaUrl: (projectId: number) => exportUrl(projectId, "prisma", "sample-prisma.svg"),
  checklistUrl: (projectId: number, guideline: "biblio" | "prisma-s") =>
    exportUrl(projectId, `checklist?guideline=${guideline}`, guideline === "biblio" ? "sample-biblio.md" : "sample-prisma-s.txt"),
  bundleUrl: (projectId: number) => exportUrl(projectId, "bundle", "sample-bundle.zip"),
};

export default api;
