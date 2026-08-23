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

const analysisResults: Record<string, Record<string, unknown>> = {
  publications: {
    total: 12,
    yearly_counts: [
      { year: 2018, count: 1 },
      { year: 2019, count: 2 },
      { year: 2020, count: 2 },
    ],
  },
  authors: {
    total_authors: 3,
    top_authors: [
      { name: "Marcus Chen Sample", pub_count: 5, citation_sum: 174 },
      { name: "Elena Garcia Sample", pub_count: 4, citation_sum: 159 },
    ],
    coauthorship_network: {
      nodes: [
        { id: 1, name: "Marcus Chen Sample", pub_count: 5 },
        { id: 2, name: "Elena Garcia Sample", pub_count: 4 },
      ],
      links: [{ source: 1, target: 2, weight: 2 }],
    },
  },
  countries: { countries: [{ country: "Netherlands", count: 4 }] },
  keywords: {
    top_keywords: [
      { term: "artificial intelligence", count: 4 },
      { term: "simulation", count: 3 },
    ],
  },
  citations: {
    total_citations: 115,
    most_cited: publications.map((publication) => ({
      title: publication.title,
      pmid: publication.pmid,
      year: publication.year,
      citation_count: publication.citation_count,
    })),
  },
  journals: { top_journals: [{ name: "Medical Education Practice", count: 4 }] },
};

export async function installMockApi(
  page: Page,
  options: { emptyWorkspace?: boolean } = {},
) {
  let emptyWorkspace = options.emptyWorkspace ?? false;
  let exclusionReason: string | null = null;

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
      return json(route, searchStatus("completed"));
    }
    if (pathname === "/api/projects/1/search" && method === "POST") {
      return json(route, searchStatus("running"), 202);
    }
    if (pathname === "/api/projects/1/search/99" && method === "GET") {
      return json(route, searchStatus("completed"));
    }
    if (pathname === "/api/projects/1/publications" && method === "GET") {
      return json(route, {
        total: publications.length,
        excluded_count: exclusionReason ? 1 : 0,
        items: publications.map((publication) =>
          publication.id === 1
            ? { ...publication, excluded: Boolean(exclusionReason), exclusion_reason: exclusionReason }
            : publication,
        ),
      });
    }
    if (/^\/api\/projects\/1\/publications\/\d+\/exclude$/.test(pathname) && method === "PATCH") {
      const body = request.postDataJSON() as { reason?: string } | null;
      exclusionReason = exclusionReason ? null : (body?.reason ?? "other");
      return json(route, { id: 1, excluded: Boolean(exclusionReason), exclusion_reason: exclusionReason });
    }
    if (pathname === "/api/projects/1/publications/bulk-exclude" && method === "POST") {
      return json(route, { excluded_count: 1, reason: "other" });
    }
    const analysisMatch = pathname.match(/^\/api\/projects\/1\/analysis\/([^/]+)$/);
    if (analysisMatch && (method === "GET" || method === "POST")) {
      const analysisType = analysisMatch[1];
      return json(route, {
        id: 1,
        project_id: 1,
        analysis_type: analysisType,
        results: analysisResults[analysisType] ?? {},
        created_at: "2026-08-23T12:00:00Z",
      });
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
}

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
