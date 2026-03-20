# BibMedEd — Bibliometric Analysis Platform for Medical Education

## Overview

A web application that enables medical education researchers to search PubMed by keywords and perform comprehensive bibliometric analysis on the results. The app automates the full pipeline: search → collect → clean → analyze → visualize → export.

**Target users:** Medical education researchers conducting bibliometric studies.

**Key value proposition:** Replaces the fragmented workflow of PubMed search + Covidence + VOSviewer + CiteSpace + Excel with a single integrated tool.

## Architecture

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js (React), D3.js (networks), Recharts (charts) |
| Backend | FastAPI (Python) |
| Database | PostgreSQL |
| Cache & Queue | Redis |
| Task Workers | Celery |
| Analysis Engine | NetworkX, pandas, scikit-learn, scipy |
| Real-time | WebSocket (via FastAPI) for progress updates |
| External APIs | PubMed E-Utilities (free), NIH iCite API (free, for citation counts) |

### System Components

```
┌─────────────────────┐     ┌─────────────────────┐     ┌──────────────┐
│  Frontend (Next.js)  │◄───►│  Backend (FastAPI)   │◄───►│  PostgreSQL  │
│                     │     │                     │     └──────────────┘
│  - Search UI        │     │  - REST API         │
│  - Dashboard        │     │  - PubMed Service   │     ┌──────────────┐
│  - D3.js Networks   │     │  - Cleaning Pipeline│◄───►│    Redis     │
│  - Recharts Charts  │     │  - Analysis Engine  │     └──────────────┘
│  - Export Manager   │     │  - Export Service   │           │
└─────────────────────┘     └─────────────────────┘           │
                                                      ┌──────────────┐
                                                      │Celery Workers│
                                                      │- PubMed Crawl│
                                                      │- Analysis    │
                                                      └──────────────┘
```

### Data Flow

1. User enters keywords in the search strategy builder
2. FastAPI dispatches PubMed search via Celery (async, handles rate limits)
3. Results are fetched, deduplicated, cleaned, and stored in PostgreSQL
4. User triggers bibliometric analysis
5. Analysis engine computes metrics and networks, caches results
6. Frontend renders interactive dashboard
7. User filters, drills down, and exports results

## Data Model

### Core Entities

**SearchProject** — A user's research project (V1 is single-user, no auth; all projects globally visible. User scoping deferred to auth feature.)
- `id`, `name`, `description`, `date_range_start`, `date_range_end`, `created_at`, `updated_at`

**SearchQuery** — Individual search execution
- `id`, `project_id` (FK), `query_string`, `database` (enum: pubmed), `status` (pending/running/completed/failed), `result_count`, `executed_at`

**Publication** — Paper metadata
- `id`, `pmid`, `doi`, `title`, `abstract`, `year`, `publication_type`, `source_database`, `citation_count` (from iCite), `fetched_at`

**Author** — Researcher
- `id`, `name`, `orcid` (nullable), `name_normalized`

**Affiliation** — Institution
- `id`, `name`, `country`, `name_normalized`

**Journal** — Publication venue
- `id`, `name`, `issn`, `e_issn`, `name_normalized`

**Keyword** — Author keywords and MeSH terms
- `id`, `term`, `type` (enum: author_keyword, mesh_term), `term_normalized`

**Citation** — Reference relationship
- `citing_publication_id` (FK), `cited_publication_id` (FK)

**AnalysisRun** — Cached analysis results
- `id`, `project_id` (FK), `analysis_type`, `parameters` (JSON), `results` (JSON), `created_at`

### Join Tables

- `publication_authors` — many-to-many, with `author_position` (integer)
- `author_affiliations` — many-to-many
- `publication_keywords` — many-to-many
- `publication_journals` — many-to-one (FK on publication)

## Bibliometric Analysis Features

### 1. Publication Trends
- Annual publication count (line/bar chart)
- Cumulative growth curve
- Year-over-year growth rate
- Filterable by country, journal, topic

### 2. Author Analysis
- Top authors by publication and citation count
- Co-authorship network (D3.js interactive force graph)
- Author productivity over time
- h-index estimation (using iCite citation counts)

### 3. Country & Institution Analysis
- Country publication rankings
- World map heatmap (choropleth)
- International collaboration network
- Top institutions leaderboard
- Institution collaboration clusters

### 4. Keyword & Theme Analysis
- Keyword co-occurrence network (D3.js)
- Thematic clusters via scikit-learn
- Keyword frequency over time (trending topics)
- MeSH term analysis
- Word cloud visualization

### 5. Citation Analysis
Citation counts and h-index data are sourced from **NIH iCite API** (free, covers all PubMed papers). PubMed itself only provides reference lists, not incoming citation counts. The citation *network* is built from reference lists within the result set (paper A cites paper B, where both are in results).
- Most cited papers leaderboard (iCite data)
- Citation network graph (within result set, from reference lists)
- Co-citation analysis
- Bibliographic coupling
- Citation burst detection

### 6. Journal Analysis
- Top publishing journals
- Journal impact metrics (derived from dataset: papers per journal, average citations per journal — not proprietary impact factor)
- Bradford's Law zones
- Journal co-citation network
- Subject category distribution

### Analysis Engine (Python Libraries)

- **NetworkX** — co-authorship, citation, keyword networks
- **pandas** — data manipulation, aggregation
- **scikit-learn** — topic clustering, burst detection
- **scipy** — statistical measures
- **Built-in** — Lotka's Law, Bradford's Law, Zipf's Law

## User Workflow & Pages

### Page 1: Home / Landing
- App introduction and value proposition
- Recent projects list
- "New Project" CTA button

### Page 2: New Project
- Project name, description, date range inputs
- Proceeds to search configuration

### Page 3: Search Configuration
- Visual boolean query builder (AND/OR/NOT operators)
- Keyword input with autocomplete (MeSH terms via NCBI MeSH Suggest API, live lookup)
- Database selection (PubMed active; Scopus/WoS shown as "coming soon")
- Date range filter
- "Run Search" button

### Page 4: Results Review
- Total result count with duplicate removal stats
- Scrollable paper list (title, authors, journal, year, citations)
- Basic sorting and filtering
- "Run Bibliometric Analysis" button to proceed

### Page 5: Analysis Dashboard (Main Screen)
- **Summary stats bar** — total publications, authors, countries, keywords, citations
- **Tabbed navigation** — Overview, Publications, Authors, Countries, Keywords, Citations, Journals
- **Overview tab** — key charts from each analysis module
- **Individual tabs** — deep dive into each analysis with interactive D3.js network visualizations
- **Global filters** — year range, publication type, country, keyword
- **Drill-down** — click any data point to see underlying papers

### Page 6: Export Manager
- PDF report (full analysis with charts and tables)
- CSV/Excel (raw data and computed metrics)
- PNG/SVG (individual charts and network visualizations)
- Shareable read-only link

## PubMed Integration

### API: NCBI E-Utilities

- **ESearch** — search PubMed and get PMIDs
- **EFetch** — fetch full records by PMIDs (XML format)
- **Rate limits** — 3 requests/second without API key, 10/second with key (free registration)
- **Pagination** — max 10,000 results per query via retstart/retmax. For queries exceeding 10,000 results, the app uses **date-slicing**: splits the date range into smaller windows, runs separate queries for each, and merges results. The user is warned that large queries take longer.

### Data Extraction from PubMed Records

From each PubMed XML record, extract:
- Title, abstract, DOI, PMID
- Author names, affiliations, ORCID (when available)
- Journal name, ISSN
- MeSH terms, author keywords
- Publication date, publication type
- Reference list (for citation network)

### Async Processing

Celery workers handle PubMed fetching in the background:
1. ESearch to get total count and PMIDs
2. Batch EFetch in groups of 200 (respecting rate limits)
3. Parse XML and store in PostgreSQL
4. Notify frontend via WebSocket when complete
5. Progress indicator shown to user

## Future Features (Deferred)

- **Scopus & Web of Science** — support with user-provided API keys
- **User authentication** — email/password + institutional SSO
- **Saved searches** — periodic re-runs to catch new publications
- **Collaboration** — shared projects between team members
- **Custom visualizations** — user-configurable chart types

## Non-Functional Requirements

- **Performance** — Dashboard loads within 2 seconds for projects up to 10,000 papers
- **Caching** — Analysis results cached per AnalysisRun; invalidated on new data
- **Responsive** — Dashboard usable on tablet (1024px+), search/results on mobile
- **Deployment** — Docker Compose for local dev; production on any cloud provider
