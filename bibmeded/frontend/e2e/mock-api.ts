import type { Page, Route } from "@playwright/test";

const project = {
  id: 1,
  name: "AI in Medical Education — Sample Project",
  description: "Synthetic records for a complete offline workflow.",
  date_range_start: "2018-01-01",
  date_range_end: "2025-12-31",
  created_at: "2026-08-23T12:00:00Z",
  updated_at: "2026-08-23T12:00:00Z",
};

const publications = [
  {
    id: 1,
    pmid: "sample-001",
    doi: "10.0000/sample.001",
    title: "Simulation-based feedback in undergraduate clinical training",
    abstract: "Synthetic demonstration record.",
    year: 2018,
    publication_type: "Article",
    citation_count: 64,
    excluded: false,
    exclusion_reason: null,
    journal_name: "Medical Education Practice",
    authors: [
      { id: 1, name: "Elena Garcia Sample", orcid: null },
      { id: 2, name: "Arun Patel Sample", orcid: null },
    ],
  },
  {
    id: 2,
    pmid: "sample-002",
    doi: "10.0000/sample.002",
    title: "Learning analytics for early identification of struggling students",
    abstract: "Synthetic demonstration record.",
    year: 2019,
    publication_type: "Article",
    citation_count: 51,
    excluded: false,
    exclusion_reason: null,
    journal_name: "Digital Health Education",
    authors: [{ id: 3, name: "Marcus Chen Sample", orcid: null }],
  },
];

// Listed by the publications route only, so the analysis mocks keep their
// contract-checked shapes; gives bulk-exclude something to count.
const uncitedPublication = {
  id: 3,
  pmid: "sample-003",
  doi: null,
  title: "A pilot curriculum for prompt engineering in residency",
  abstract: "Synthetic demonstration record.",
  year: 2025,
  publication_type: "Article",
  citation_count: 0,
  excluded: false,
  exclusion_reason: null,
  journal_name: "Digital Health Education",
  authors: [{ id: 4, name: "Noor Haddad Sample", orcid: null }],
};

// Shapes are checked against the real backend by api-contract.spec.ts; refresh
// fixtures/api-shapes.json as described in CONTRIBUTING.md when the API changes.
export const analysisResults: Record<string, Record<string, unknown>> = {
  publications: {
    schema_version: "1.0",
    total: 12,
    yearly_counts: [
      { year: 2018, count: 1 },
      { year: 2019, count: 2 },
      { year: 2020, count: 2 },
    ],
    growth_rates: [
      { year: 2019, rate: 100 },
      { year: 2020, rate: 0 },
    ],
    cumulative: [
      { year: 2018, cumulative: 1 },
      { year: 2019, cumulative: 3 },
      { year: 2020, cumulative: 5 },
    ],
    field_maturity: {
      phase: "growing",
      carrying_capacity: 14.2,
      midpoint_year: 2021.4,
      growth_rate: 0.512,
      fit_quality: 0.981,
      progress: 0.352,
      method: "logistic-growth (Bettencourt & Kaur 2011)",
    },
    growth_summary: {
      cagr: 41.42,
      doubling_time_years: 2,
      start_year: 2018,
      end_year: 2020,
      excluded_current_year: false,
      reason: null,
    },
  },
  authors: {
    schema_version: "1.0",
    total_authors: 3,
    top_authors: [
      {
        id: 1,
        name: "Marcus Chen Sample",
        orcid: null,
        pub_count: 5,
        citation_sum: 174,
        h_index: 5,
        g_index: 5,
        e_index: 12.2,
      },
      {
        id: 2,
        name: "Elena Garcia Sample",
        orcid: null,
        pub_count: 4,
        citation_sum: 159,
        h_index: 4,
        g_index: 4,
        e_index: 12.4,
      },
    ],
    coauthorship_network: {
      nodes: [
        { id: 1, name: "Marcus Chen Sample", pub_count: 5 },
        { id: 2, name: "Elena Garcia Sample", pub_count: 4 },
      ],
      links: [{ source: 1, target: 2, weight: 2 }],
    },
  },
  countries: {
    schema_version: "1.0",
    country_counts: [
      { country: "Netherlands", count: 4 },
      { country: "Canada", count: 5 },
    ],
    institution_counts: [
      { institution: "Sample Department of Medical Education, University of Toronto", count: 5 },
    ],
    collaboration_network: {
      nodes: [
        { id: "Netherlands", count: 4 },
        { id: "Canada", count: 5 },
      ],
      links: [{ source: "Canada", target: "Netherlands", weight: 1 }],
    },
  },
  keywords: {
    schema_version: "1.0",
    top_keywords: [
      { term: "artificial intelligence", count: 4 },
      { term: "simulation", count: 3 },
    ],
    cooccurrence_network: {
      nodes: [
        { id: "artificial intelligence", count: 4, label: "artificial intelligence" },
        { id: "simulation", count: 3, label: "simulation" },
      ],
      links: [{ source: "artificial intelligence", target: "simulation", weight: 1 }],
    },
    keyword_trends: [
      {
        term: "artificial intelligence",
        trend: [
          { year: 2019, count: 1 },
          { year: 2021, count: 1 },
        ],
      },
    ],
    burst_terms: [{ term: "generative AI", year: 2024, count: 3, intensity: 2.4, baseline_share: 0.0625 }],
  },
  citations: {
    schema_version: "1.0",
    total_citations: 115,
    most_cited: publications.map((publication) => ({
      title: publication.title,
      pmid: publication.pmid,
      year: publication.year,
      citation_count: publication.citation_count,
    })),
    citation_network: {
      nodes: publications.map((publication) => ({
        id: publication.id,
        pmid: publication.pmid,
        title: publication.title,
        year: publication.year,
        citations: publication.citation_count,
      })),
      links: [{ source: 2, target: 1 }],
    },
    coupling_network: { nodes: [], links: [] },
    coupling_truncated: false,
    cocitation_network: { nodes: [], links: [] },
    cocitation_truncated: false,
  },
  journals: {
    schema_version: "1.0",
    top_journals: [{ name: "Medical Education Practice", pub_count: 4, avg_citations: 43.3 }],
    bradford_zones: [{ zone: 1, journal_count: 1, article_count: 4 }],
    total_journals: 1,
  },
};

export function analysisRunResponse(analysisType: string) {
  return {
    id: 1,
    project_id: 1,
    analysis_type: analysisType,
    results: analysisResults[analysisType] ?? {},
    created_at: "2026-08-23T12:00:00Z",
  };
}

export interface MockApiOptions {
  emptyWorkspace?: boolean;
  readOnly?: boolean;
  configUnavailable?: boolean;
  missingAnalyses?: string[];
  sampleSearch?: boolean;
}

export async function installMockApi(page: Page, options: MockApiOptions = {}) {
  let emptyWorkspace = options.emptyWorkspace ?? false;
  const readOnly = options.readOnly ?? false;
  const writeRequests: string[] = [];
  let exclusionReason: string | null = null;
  let uncitedExcluded = false;

  // Keep E2E deterministic and offline: icon-font availability must not turn
  // an application-flow test into a third-party network test.
  await page.route("https://fonts.googleapis.com/**", (route) =>
    route.fulfill({ status: 200, contentType: "text/css", body: "" }),
  );

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname } = url;
    const method = request.method();

    if (pathname === "/api/config" && method === "GET") {
      return options.configUnavailable
        ? json(route, { detail: "Internal server error" }, 500)
        : json(route, { read_only: readOnly });
    }
    if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
      writeRequests.push(`${method} ${pathname}`);
      if (readOnly) return json(route, { detail: "read-only demo", read_only: true }, 403);
    }

    if (pathname === "/api/projects" && method === "GET") {
      return json(route, emptyWorkspace ? [] : [project]);
    }
    if (pathname === "/api/projects/sample" && method === "POST") {
      emptyWorkspace = false;
      return json(route, project, 201);
    }
    if (pathname === "/api/projects" && method === "POST") {
      return json(route, project, 201);
    }
    if (pathname === "/api/projects/1" && method === "GET") {
      return json(route, project);
    }
    if (pathname === "/api/projects/1" && method === "DELETE") {
      emptyWorkspace = true;
      return route.fulfill({ status: 204, body: "" });
    }
    if (pathname === "/api/adapters" && method === "GET") {
      return json(route, [
        { name: "pubmed", display_name: "PubMed", requires_api_key: false },
        { name: "openalex", display_name: "OpenAlex", requires_api_key: false },
        { name: "lens", display_name: "Lens.org", requires_api_key: true },
      ]);
    }
    if (pathname === "/api/projects/1/search/latest" && method === "GET") {
      return json(
        route,
        options.sampleSearch
          ? { ...searchStatus("completed"), query_string: sampleQueryString, database: "sample" }
          : searchStatus("completed"),
      );
    }
    if (pathname === "/api/projects/1/search" && method === "POST") {
      return json(route, searchStatus("running"), 202);
    }
    if (pathname === "/api/projects/1/search/99" && method === "GET") {
      return json(route, searchStatus("completed"));
    }
    if (pathname === "/api/projects/1/publications" && method === "GET") {
      return json(route, {
        total: publications.length + 1,
        excluded_count: (exclusionReason ? 1 : 0) + (uncitedExcluded ? 1 : 0),
        items: [
          ...publications.map((publication) =>
            publication.id === 1
              ? { ...publication, excluded: Boolean(exclusionReason), exclusion_reason: exclusionReason }
              : publication,
          ),
          uncitedExcluded ? { ...uncitedPublication, excluded: true, exclusion_reason: "other" } : uncitedPublication,
        ],
      });
    }
    if (/^\/api\/projects\/1\/publications\/\d+\/exclude$/.test(pathname) && method === "PATCH") {
      const body = request.postDataJSON() as { reason?: string } | null;
      exclusionReason = exclusionReason ? null : (body?.reason ?? "other");
      return json(route, { id: 1, excluded: Boolean(exclusionReason), exclusion_reason: exclusionReason });
    }
    if (pathname === "/api/projects/1/publications/bulk-exclude" && method === "POST") {
      const newlyExcluded = uncitedExcluded ? 0 : 1;
      uncitedExcluded = true;
      return json(route, { excluded_count: newlyExcluded, reason: "other" });
    }
    const analysisMatch = pathname.match(/^\/api\/projects\/1\/analysis\/([^/]+)$/);
    if (analysisMatch && (method === "GET" || method === "POST")) {
      const analysisType = analysisMatch[1];
      if (method === "GET" && options.missingAnalyses?.includes(analysisType)) {
        return json(route, { detail: "Analysis not found. Run it first." }, 404);
      }
      return json(route, analysisRunResponse(analysisType));
    }
    if (pathname === "/api/projects/1/export/methodology") {
      return route.fulfill({
        status: 200,
        contentType: "text/plain; charset=utf-8",
        body: "BibMedEd methodology log\nRecords identified: 12\nRecords included: 11\n",
      });
    }
    if (pathname === "/api/projects/1/export/prisma") {
      return route.fulfill({
        status: 200,
        contentType: "image/svg+xml",
        body: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 120"><title>PRISMA flow</title><text x="20" y="60">12 identified → 11 included</text></svg>',
      });
    }
    if (pathname.startsWith("/api/projects/1/export/")) {
      return route.fulfill({
        status: 200,
        contentType: "text/plain",
        headers: { "content-disposition": 'attachment; filename="bibmeded-export.txt"' },
        body: "sample export",
      });
    }

    return json(route, { detail: `Unhandled mock route: ${method} ${pathname}` }, 404);
  });

  return { writeRequests };
}

export const sampleQueryString =
  '("Education, Medical"[Mesh] OR "medical education"[tiab]) AND ("Artificial Intelligence"[Mesh] OR "machine learning"[tiab] OR "generative AI"[tiab] OR "learning analytics"[tiab] OR "simulation"[tiab] OR "virtual patient*"[tiab]) AND ("2018/01/01"[PDAT] : "2025/12/31"[PDAT])';

function searchStatus(status: string) {
  return {
    query_id: 99,
    status,
    result_count: 12,
    raw_result_count: 12,
    duplicate_count: 0,
    progress: 100,
  };
}

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}
