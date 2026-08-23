# Changelog

All notable changes to BibMedEd are recorded here. This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] — 2026-08-23

### Added

- Added a deterministic, network-free synthetic sample workflow (`POST /api/projects/sample`) with 12 records, meaningful author/country/keyword/citation networks, screening state, and a reproducible methodology trace. Repeated requests reopen the same sample instead of creating unbounded copies.
- Added the `bibmeded search --dry-run` CLI for estimating an upstream result count without fetching or persisting records ([#17](https://github.com/ata381/BibMedEd/issues/17)).
- Added full `bibmeded search` execution through the existing database and Celery pipeline, including year and result-limit options ([#52](https://github.com/ata381/BibMedEd/pull/52)).
- Added Lens.org Scholarly as the fifth built-in source, with token-based configuration, pagination, record mapping, fixture-based tests, and empty-result handling ([#14](https://github.com/ata381/BibMedEd/issues/14)).

### Changed

- Improved first-run usability with a homepage shortcut that creates the sample project and opens its analysis dashboard immediately.
- Updated the homepage, documentation, and adapter registry to reflect all five built-in sources.
- Clarified how newcomers claim work, how adapter auto-discovery works, and what a complete adapter contribution includes.

### Fixed

- Replaced CLI tracebacks for unknown sources and network failures with actionable stderr messages and non-zero exit codes ([#50](https://github.com/ata381/BibMedEd/pull/50)).
- Prevented full CLI searches from polling forever when adapter construction fails.
- Handled empty Lens.org result pages without raising an indexing error.

### Security

- Updated Next.js and its matching lint configuration from 16.2.9 to 16.3.1, then refreshed transitive dependencies so `npm audit` reports zero known vulnerabilities.

### Community

- Thank you to [@BaygeldiAza](https://github.com/BaygeldiAza) for the dry-run and full CLI search contributions ([#46](https://github.com/ata381/BibMedEd/pull/46), [#52](https://github.com/ata381/BibMedEd/pull/52)).
- Thank you to [@landon-personal](https://github.com/landon-personal) for improving CLI source and network error handling ([#50](https://github.com/ata381/BibMedEd/pull/50)).

## [0.2.0] — 2026-05-28

A research-grade hardening release. Ten thorough multi-agent review rounds (3-7
parallel agents each, plus persona-based outside-in audits and inter-round drift
checks) drove 200+ commits worth of findings into ~10 focused commits across the
following themes.

### Added

- **Fourth bibliographic adapter — Semantic Scholar.** `app/adapters/semantic_scholar.py`. Free-tier Graph API v1 access (~100 req/5min); pass an API key for the keyed tier. Auto-discovered by the registry alongside PubMed / OpenAlex / CrossRef — no `__init__.py` registration step. `/paper/batch` requests chunked at 500 IDs upstream cap; offset pagination terminates at the inclusive `9999` upstream limit.
- **Per-author bibliometric indices.** `h-index` (Hirsch 2005), `g-index` (Egghe 2006), and `e-index` (Zhang 2009) computed alongside `pub_count` and `citation_sum` for every author in `analyze_authors`. `top_authors` sorted by h-index with citation_sum and pub_count as tie-breakers. Indices are corpus-scoped (within the project's deduplicated record set), documented on the function and in `paper.md`.
- **Bibliographic coupling and co-citation networks** (`analyze_citations`). Kessler (1963) coupling — pairs of papers weighted by shared references; Small (1973) co-citation — pairs of papers weighted by shared citing papers. Computed against in-corpus references stored in the new `Publication.external_references` JSON column. Final networks capped at the top 100 strongest pairs; hub-degree cap at 75 prevents O(N²) explosion on highly-cited seminal papers.
- **Keyword burst detection.** Share-ratio heuristic in the spirit of Kleinberg (2003) — surfaces statistically sudden surges in keyword frequency for the "research frontiers" reporting common to bibliometric papers. Documented with explicit `intensity` and `baseline_share` units in the API and `paper.md`.
- **Logistic-growth field-maturity classification** (`analyze_publication_trends`). Fits a logistic curve via SciPy Levenberg-Marquardt to the cumulative-yearly-publications series and classifies the field as emerging / growing / mature / saturating. Forces `phase="undetermined"` when R² < 0.85 so a poorly-fit corpus doesn't get confidently mislabeled. Cites Bettencourt & Kaur 2011.
- **PRISMA 2020 exclusion reasons.** New `Publication.exclusion_reason` column with a nine-category Literal (`wrong_study_design`, `wrong_population`, `wrong_intervention`, `wrong_outcome`, `not_peer_reviewed`, `non_english`, `duplicate`, `fulltext_unavailable`, `other`). Toggle-exclude UI opens a 9-option PRISMA reason menu; bulk-exclude stamps every row with a configurable reason. Methodology log surfaces the per-reason breakdown ("MANUAL EXCLUSIONS BY REASON" section), and the PRISMA SVG side-box renders the reason breakdown — addressing PRISMA 2020 item 17.
- **JSON export endpoint** (`GET /api/projects/{id}/export/json`). Versioned single-object payload with explicit per-publication schema (`pmid`, `doi`, `title`, `abstract`, `year`, `authors`, `keywords`, `excluded`, `exclusion_reason`, etc.). Stable `schema_version` field for downstream pinning. Same shape is included in the export bundle .zip.
- **Single-click submission bundle** (`GET /api/projects/{id}/export/bundle`). Returns a `.zip` containing the CSV, RIS, JSON, methodology .txt, PRISMA .svg, and a `MANIFEST.txt`. Documented as "what a JOSS / systematic review reviewer needs to reproduce the methodology in one download."
- **Versioned analysis responses.** Every `analyze_*` response is stamped with `ANALYSIS_SCHEMA_VERSION = "1.0"` so programmatic users can pin against a known dict shape. Additive changes (new optional keys) don't bump the version; breaking changes do.
- **Liveness + readiness probes.** `GET /api/live` (no I/O, always 200) and `GET /api/ready` (deep DB+Redis ping, 503 on failure). Documented in `docs/deploy.md` with a docker-compose `healthcheck.test` snippet.
- **Request correlation.** Every API request carries an `X-Request-ID` (generated unless the client supplies one) propagated through a `ContextVar` and stamped on every log line. 500 responses include the id in the body so users can quote it without log access.
- **Scripting docs page** (`docs/scripting.md`). End-to-end Jupyter example for driving BibMedEd from a notebook — project creation, search dispatch, status polling, analysis, JSON export, bulk batching via asyncio, pandas/polars integration, courtesy-tier env vars.
- **PRISMA cap-notice banner.** Results page warns when the upstream record count exceeds what BibMedEd actually fetched, with an explicit "silently truncating a systematic review's record set is not journal-acceptable" note so the cap is never invisible.
- **Mobile responsive layout.** Sidebar collapses to an off-canvas drawer with a hamburger toggle below `md`; main content reclaims the full viewport; PRISMA flow row scrolls horizontally instead of clipping.
- **Alembic baseline migration** (`alembic/versions/0001_baseline.py`). Captures the v0.2.0 schema state so production deploys have a migration path beyond `create_all`. Existing dev databases use `alembic stamp 0001_baseline`.

### Fixed

- **Cross-source deduplication was dead code.** `deduplicate_cross_source` existed in `app/services/cleaning.py` but was never called from the worker; the only existence check was a per-source `pmid` lookup that misses DOI duplicates across sources. The worker now invokes `deduplicate_cross_source` before persisting, logs the per-field breakdown as a `dedup` methodology step, and checks both `pmid` AND `doi` when looking up existing rows.
- **IDOR on `toggle-exclude`.** The endpoint fetched a `Publication` by id without verifying it belonged to the URL's `project_id`. Now scoped via `pub.query_id in project.queries`.
- **Per-record SAVEPOINT cache poisoning.** When a record's SAVEPOINT rolled back, the in-memory `authors_by_norm` / `affils_by_norm` / `keywords_by_key` / journal identity-map entries retained ORM objects whose underlying rows had been undone. Subsequent records in the same batch hit phantom FK targets. The worker now tracks every cache key added during a record and evicts them on rollback.
- **`OperationalError` / `DisconnectionError` were silently swallowed** by the per-record `except Exception` in `_persist_records`, so a dropped DB connection mid-batch silently undercounted the methodology log. These fatal exceptions now propagate immediately.
- **PRISMA SVG `included` count was stale.** The diagram used the last methodology step's `records_out`, which is the pre-manual-exclusion count. The PRISMA endpoint now passes the live `excluded == False` row count as `included_override` so manual exclusions flow through the diagram.
- **Burst-detection denominator double-counted.** `total_per_year` incremented per-keyword-occurrence (a publication with 8 keywords contributed 8) instead of per-unique-keyword (should contribute 1 per pub). Burst intensity scores were systematically depressed in high-keyword years.
- **Case-sensitive `Journal.name` lookup** would create separate `"JAMA"` and `"Jama"` rows. Lookup now uses `Journal.name_normalized`.
- **`duplicate_count` semantics**: the field conflated cross-source dedup, DB-existing skips, and per-record exceptions. Now reflects only cross-source dedup; other causes are visible in the methodology log's `records_in - records_out` deltas.
- **g-index off-by-one regression-guarded** with the canonical Egghe-borrowing test case (`[10, 4, 4, 4, 4, 0] → g=5`) confirming the loop's `break` is provably safe for sorted-descending citation lists.
- **Search-router `httpx.AsyncClient` leak.** `trigger_search` was instantiating an adapter just to validate the `source` name, leaking one connection pool per request for non-PubMed sources. Pydantic's `Literal["pubmed","openalex","crossref","semanticscholar"]` already validates upstream; the redundant probe was removed.
- **Two HIGH bugs caught by reviewer audit between rounds**: cap-notice banner used the wrong arithmetic (`total` vs `result_count + duplicate_count`), and the search-step `searched_at` timestamp used `.replace(tzinfo=utc)` instead of `.astimezone(utc)` which would corrupt Postgres timezone-aware datetimes.
- **`PublicationResponse.exclusion_reason` strict Literal crashed serialization** for any legacy DB row with an unrecognized reason string, and the list endpoint's bare `except Exception: continue` silently dropped the publication. Now coerces unknown values to `"other"` via a `field_validator(mode="before")`.
- **`external_references` non-list values** (legacy JSON column with a scalar) crashed the bibliographic-coupling analysis. Now guarded with `isinstance(... , list)`.
- **JOSS authorship inconsistency.** `docs/index.md` bibtex example had the wrong author name (`Ata, Aakil` instead of `Akillioglu, Ata`). Anyone citing the project from the docs homepage would have credited the wrong person.
- **AdapterSource Literal didn't include the new Semantic Scholar adapter** — the adapter was registered but rejected by Pydantic at the search endpoint until R9. Now reachable end-to-end.

### Performance

- **N+1 elimination in the ingestion path.** `_persist_records` now bulk-prefetches Authors, Affiliations, and Keywords per batch via `WHERE name_normalized IN (...)` queries. For a 200-record batch averaging 5 authors each, this collapses ~2000 per-record SELECTs into 4 batch queries.
- **`normalize_name` memoized within a batch** so each unique string is normalized once instead of 2-3x per author per record.
- **iCite enrichment bulk-update.** Was issuing one SELECT per PMID in a loop; now a single `Publication.pmid.in_(citation_counts)` lookup updates all matching rows.
- **DB indexes for hot filters.** `Publication.query_id` (every list/analysis filter), `Publication.doi` (dedup + coupling join), `Publication.excluded` (bulk-exclude predicate), `Author.name_normalized`, `Keyword.term_normalized`, `Affiliation.country`. Critical: previously every `list_publications` call was a full table scan.
- **`joinedload(Publication.authors)`** in `analyze_authors` — was firing one SELECT per publication when iterating authors.
- **D3 cooccurrence / coauthor pairs built directly into `Counter`** instead of accumulating a list and re-counting.
- **`Math.max(...arr)` → `arr.reduce(...)`** in force-graph to avoid V8's argument limit on large co-authorship networks.

### Security

- **Pydantic `Literal` validation everywhere.** `SearchRequest.source`, `ExclusionReason`, etc. rather than free-form strings.
- **Bounded `max_results`** on `SearchRequest` (1-10000) — prevented an unbounded-memory worker DoS via a single API call.
- **PubMed XML parser hardened** with `resolve_entities=False`, `no_network=True`, `load_dtd=False`, `huge_tree=False`. Closes a latent XXE vector if a future NCBI response or compromised proxy ever returns a DOCTYPE.
- **HTTP 400 response no longer echoes user input.** `routers/analysis.py` previously reflected the raw `analysis_type` segment into the response body and any log aggregator's response-body index. Now uses a fixed string + a `%r`-repr log line that prevents CRLF expansion.
- **Frontend `window.open` everywhere uses `noopener,noreferrer`** — the export page had 6 buttons skipping these flags, which is a tabnapping vector.

### Accessibility

- Heading hierarchy fixed (`h1` on every page top), every PRISMA / sidebar / dashboard icon marked `aria-hidden` so screen readers no longer announce raw ligature names ("arrow_forward arrow_forward arrow_forward"), Material icons in action buttons all hidden, exclude-reason dropdown menu has full ARIA-menu pattern + Escape-to-close + first-item focus on open + click-outside via `click` (not `mousedown`) to avoid a known close-then-reopen race.
- **`react-hot-toast` toasts now reach assistive tech.** Default `aria-live="off"` was silencing every "Publication excluded" / "Bulk exclude failed" — success/info toasts are now `polite`, errors `assertive`.
- **Per-publication `aria-label` on exclude/include button** so 20 identical "Included" buttons on a result page can be disambiguated by screen reader.
- **Force-graph SVG** gains `role="img"` + a descriptive `aria-label` plus a visually-hidden top-10-nodes summary table — accessible alternative to the interactive D3 layout.
- **Search-progress region** is now `role="status" aria-live="polite"` — "Fetched X of Y records" announcements reach NVDA users without sighted help.
- **Pagination prev/next** carry `aria-label`s and `aria-current="page"` on the active number.
- **Cap-notice banner** uses `role="status"` and hides the warning icon from screen readers (it duplicates the visible text).

### Observability

- Module-level loggers added to every router (`projects`, `search`, `publications`, `analysis`, `export`, `adapters`) — 5 of 6 previously had none.
- Phase-transition INFO logs in `app/workers/tasks.py` — search-complete, run-complete include the record counts so an SRE can see where a stuck task is in the pipeline.
- `logger.exception` in the outer Celery exception handler attributes the traceback to the failing `query_id` for Sentry / structured aggregators.
- `bare raise` (not `raise e`) so production tracebacks point at the original failure site, not the re-raise line.

### Documentation

- `paper.md`: dedup algorithm fully described, operational 2,000-record ceiling rationalized, programmatic-access surface documented, h/g/e and field-maturity citations added (Hirsch 2005, Egghe 2006, Zhang 2009, Bettencourt & Kaur 2011, Kinney et al. 2023).
- `paper.bib`: 4 new citations.
- `CONTRIBUTING.md`: dropped the false `app/adapters/__init__.py` registration step (the registry auto-discovers; nothing to register), added an explicit "load-bearing invariants" callout for the two undocumented contracts (lowercase DOIs, explicit empty `mesh_terms` for non-PubMed adapters).
- `app/adapters/base.py`: `RawRecord` docstring rewritten with all four load-bearing invariants in one place.
- `app/adapters/registry.py`: module docstring explains the "drop a file, no registration needed" contributor workflow.
- `docs/scripting.md` (new), `docs/deploy.md` (Docker-Desktop onboarding + liveness/readiness probes), `docs/index.md` (BibTeX author name corrected).

### Removed

- **`ProjectListResponse` schema** — defined but never used, never imported. Pure dead code.
- **`SearchRequest.database` field** — duplicated `source` and was silently ignored.
- **hI-norm placeholder docstring** in `_compute_indices` — the function never returned `hI_norm`; the docstring promised a metric the code didn't compute.

### Test coverage

`pytest` is now 143 tests, up from 104 (round-0 baseline). New coverage:

- `test_health.py`: 6 tests (liveness, readiness with mocked Redis up/down, request-id round-trip, request-id generation).
- `test_adapters_semantic_scholar.py`: 15 tests covering DOI lowercase invariant, PMID propagation, ORCID URL stripping, reference lowercasing, offset-cap inclusive boundary, paginated year filter, `/paper/batch` 500-id chunking, non-list error responses.
- `test_adapters_registry.py`: regression guard for the four shipped adapters.
- `test_analysis_authors.py`: h/g/e indices, including the canonical Egghe-borrowing case `[10,4,4,4,4,0] → g=5`.
- `test_analysis_publications.py`: field_maturity logistic fit + abstain path.
- `test_analysis_citations.py`: bibliographic coupling + co-citation pair semantics.
- `test_prisma.py`: per-reason exclusion breakdown, `included_override` precedence.
- `test_routers_publications.py`: PRISMA exclusion-reason workflow.

### Planned
- Adapters: Europe PMC, arXiv, DOAJ, OpenCitations, CORE, BASE, Lens.org — see [`GOOD_FIRST_ISSUES.md`](GOOD_FIRST_ISSUES.md).
- i18n scaffold + Turkish locale ([#16](https://github.com/ata381/BibMedEd/issues/16)).
- Search CLI `--dry-run` for cost estimation ([#17](https://github.com/ata381/BibMedEd/issues/17)).
- Two-reviewer screening workflow (currently single-reviewer toggle exclusion).
- Title/abstract vs full-text screening-stage distinction (PRISMA 2020 splits these; currently one binary `excluded` flag).
- Prometheus metrics endpoint (defer until a Grafana consumer exists).
- `/api/health/detail` debug surface with row counts + Celery worker count.
- Dashboard tab a11y: switch from inline `<button>` group to the existing `Tabs` primitive.

---

## [0.1.2] — 2026-05-27

**Zenodo DOI:** [10.5281/zenodo.20404322](https://doi.org/10.5281/zenodo.20404322) · [Release](https://github.com/ata381/BibMedEd/releases/tag/v0.1.2)

Operational release that triggered the first Zenodo archive once the repo's Zenodo↔GitHub integration was enabled.

### Added
- Zenodo concept DOI ([10.5281/zenodo.20404321](https://doi.org/10.5281/zenodo.20404321)) and version DOI for v0.1.2.
- Zenodo badge in README; `doi:` field in `CITATION.cff`; DOI in the README BibTeX example.
- `docs/why-bibmeded.md` — capability comparison vs Covidence, VOSviewer, CiteSpace, Bibliometrix, pyBibX.
- `docs/case-study.md` — end-to-end worked example covering query → analyses → methodology log.

## [0.1.1] — 2026-05-27

**Zenodo DOI:** [10.5281/zenodo.20404321](https://doi.org/10.5281/zenodo.20404321) (concept) · [Release](https://github.com/ata381/BibMedEd/releases/tag/v0.1.1)

### Fixed
- Wired the maintainer's real ORCID (`0009-0005-4533-4594`) into `CITATION.cff`, `paper.md`, and `.zenodo.json`. Unblocks JOSS submission.

## [0.1.0] — 2026-05-27

**Release:** https://github.com/ata381/BibMedEd/releases/tag/v0.1.0

First tagged public release.

### Added
- **Multi-database search.** PubMed (NCBI E-utilities) and OpenAlex adapters with auto-discovery via the adapter registry.
- **Cross-source deduplication** by DOI and PMID, with normalised identifier matching (case-insensitive DOI, prefix-stripped, whitespace-trimmed PMID).
- **Six bibliometric analysis modules**: publications-over-time, author productivity, country distribution, keyword co-occurrence (case-normalised), citation impact, journal ranking.
- **Interactive D3.js networks** for co-authorship and keyword co-occurrence.
- **Reproducible methodology log** — every pipeline step recorded and exportable as a plain-text file for PRISMA Methods sections.
- **Standard exports**: `.RIS`, `.CSV`, methodology log.
- **One-command self-host**: `docker compose up` for FastAPI + Celery + Postgres + Redis + Next.js frontend.
- **One-click cloud deploy**: Render.com Blueprint.
- **Adapter SDK**: ~50-line Python contract to add any bibliographic source.
- **Project infrastructure**: CI on Python 3.12/3.13 backend, Next.js frontend build, Docker smoke, MkDocs `--strict`; Code of Conduct, security policy, contribution guide, public roadmap; issue and PR templates; JOSS paper draft.
- **Twelve `good first issue` tickets** opened to seed the contributor pipeline.

### Changed
- Dropped pandas from the analysis path; replaced with `collections.Counter` for a smaller install footprint.
- Cleanup: removed PDFs, docx, and internal dev plans from the repo tree.

### Security
- Hardened the global error handler so exception types no longer leak in API responses.
- Added `rel="noopener noreferrer"` to `window.open` in the export page (tabnabbing defence).

[Unreleased]: https://github.com/ata381/BibMedEd/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/ata381/BibMedEd/releases/tag/v0.3.0
[0.2.0]: https://github.com/ata381/BibMedEd/releases/tag/v0.2.0
[0.1.2]: https://github.com/ata381/BibMedEd/releases/tag/v0.1.2
[0.1.1]: https://github.com/ata381/BibMedEd/releases/tag/v0.1.1
[0.1.0]: https://github.com/ata381/BibMedEd/releases/tag/v0.1.0
