export const DATA_SOURCES = [
  "PubMed",
  "OpenAlex",
  "CrossRef",
  "Semantic Scholar",
  "Lens.org",
] as const;

export const ANALYSIS_MODULES = [
  "Publications",
  "Authors",
  "Countries",
  "Keywords",
  "Citations",
  "Journals",
] as const;

export const WORKFLOW_STEPS = [
  { suffix: "search", label: "Search", description: "Build and run the query" },
  { suffix: "results", label: "Results", description: "Screen and deduplicate" },
  { suffix: "dashboard", label: "Dashboard", description: "Six bibliometric analyses" },
  { suffix: "export", label: "Export", description: "Data, methodology, PRISMA" },
] as const;

export const REPO_URL = "https://github.com/ata381/BibMedEd";
export const DOCS_URL = "https://ata381.github.io/BibMedEd/";
