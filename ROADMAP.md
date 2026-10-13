# BibMedEd Roadmap

A living document. Items move up and down as the community contributes adapters and bug reports.

## Merged since 0.4.0 (unreleased)

- [x] Append-only screening decision log with reviewer labels, reported in the methodology export and the bundle ([#120](https://github.com/ata381/BibMedEd/issues/120))
- [x] Lotka's law fit in the authors analysis and the methodology export ([#61](https://github.com/ata381/BibMedEd/issues/61))
- [x] Web of Science plain-text export for VOSviewer and Bibliometrix, with author order preserved ([#68](https://github.com/ata381/BibMedEd/issues/68), [#159](https://github.com/ata381/BibMedEd/issues/159))
- [x] Troubleshooting and FAQ page ([#67](https://github.com/ata381/BibMedEd/issues/67))
- [x] PubMed: key-dependent request rate, compose forwards every source setting, requests identify the tool and contact email ([#148](https://github.com/ata381/BibMedEd/issues/148), [#156](https://github.com/ata381/BibMedEd/issues/156)); CSV keeps a missing citation count empty ([#160](https://github.com/ata381/BibMedEd/issues/160))
- [x] Dependabot patch updates auto-merge behind full CI; JOSS AI-usage disclosure in `paper.md`
- [x] Title/abstract vs full-text screening stages in exclusions, the PRISMA diagram and the methodology log ([#91](https://github.com/ata381/BibMedEd/issues/91))
- [x] CAGR and doubling time in the publication-trends analysis and on the dashboard ([#62](https://github.com/ata381/BibMedEd/issues/62), [#113](https://github.com/ata381/BibMedEd/issues/113))
- [x] Table-driven required-key adapter configuration ([#88](https://github.com/ata381/BibMedEd/issues/88))
- [x] Accessible ConfirmDialog replacing native `confirm()` ([#90](https://github.com/ata381/BibMedEd/issues/90))
- [x] Sample project ships a stored search query ([#94](https://github.com/ata381/BibMedEd/issues/94))
- [x] Engineering hygiene: e2e mock contract check ([#78](https://github.com/ata381/BibMedEd/issues/78)), persist-loop SAWarning ([#87](https://github.com/ata381/BibMedEd/issues/87)), `request_id_ctx` import cycle ([#98](https://github.com/ata381/BibMedEd/issues/98)), publication-list pagination tie-breaker ([#118](https://github.com/ata381/BibMedEd/issues/118))

## 0.4.0 — shipped 2026-09-30

- [x] Journal-editorial frontend redesign with WCAG 2.2 fixes (#75)
- [x] `BIBMEDED_READ_ONLY` mode for safely exposing a demo (#81)
- [x] One-command local read-only demo, plus a free-plan Render Blueprint for a public demo (#86)
- [x] `pip install bibmeded` lightweight CLI on PyPI, with `--version` and `sources` commands (#84, #72, #71)
- [x] Python package renamed `app` -> `bibmeded` (#97)

A hosted public demo is deliberately deferred; the Blueprint ships, but no public instance is deployed yet.

## Shipped in 0.3.0 (2026-08-23)

- [x] Five adapters: PubMed, OpenAlex, CrossRef, Semantic Scholar, Lens.org — with cross-source DOI / PMID deduplication
- [x] Six analysis modules (publications, authors, countries, keywords, citations, journals)
- [x] Per-author h-index, g-index, e-index — cited (Hirsch 2005, Egghe 2006, Zhang 2009)
- [x] Bibliographic coupling + co-citation networks (Kessler 1963, Small 1973)
- [x] Keyword burst detection
- [x] Logistic field-maturity classification (Bettencourt & Kaur 2011) with R²-gated confidence
- [x] D3.js co-authorship + keyword co-occurrence + coupling + co-citation networks
- [x] PRISMA 2020 flow diagram export with per-reason exclusion breakdown
- [x] PRISMA 2020 exclusion reasons (9-category Literal)
- [x] Standard exports: CSV, RIS, JSON (versioned), methodology .txt, PRISMA .svg, single-click .zip bundle
- [x] Versioned analysis responses (`schema_version` field)
- [x] Liveness + readiness probes (`/api/live`, `/api/ready`)
- [x] Request-ID correlation across API + Celery
- [x] OpenAPI Swagger docs surfaced at `/docs`, scripting guide for notebook users
- [x] Alembic baseline migration
- [x] Mobile-responsive UI (off-canvas drawer below md, responsive PRISMA flow)
- [x] WCAG 2.2 a11y pass (heading hierarchy, ARIA menus, aria-live for dynamic state, force-graph alt text)
- [x] One-click Render.com deploy
- [x] CI on every PR (Python 3.12 / 3.13, frontend lint + tsc + build, Docker build)
- [x] Bundled synthetic sample project for network-free first-run exploration
- [x] Command-line dry-run estimates and full search execution

## Now (0.5) — toward the first published use

Order set on 2026-10-14 after a needs review of the literature on bibliometric and systematic-review tooling. The findings in one paragraph: the best-documented pain is reporting and reproducibility, not a shortage of tools (BIBLIO and PRISMA-S checklists, journals starting to require them, about a tenth of published searches reproducible); the second is licence-free data access, where OpenAlex is credible but has no non-programmer interface and known affiliation and author-identity defects; dual-reviewer screening and AI extraction are already served or regulated. The papers this project serves appear mostly in nursing-education and open-access clinical journals, and JOSS pre-review [#10680](https://github.com/openjournals/joss-reviews/issues/10680) asks for one published research use before resubmission.

- [ ] Reporting-checklist export (BIBLIO, PRISMA-S appendix) filled from the methodology log ([#166](https://github.com/ata381/BibMedEd/issues/166))
- [ ] Fuzzy-match deduplication with every decision logged ([#167](https://github.com/ata381/BibMedEd/issues/167))
- [ ] Author harmonisation on ORCID and source ids, with an exportable thesaurus ([#168](https://github.com/ata381/BibMedEd/issues/168)); fixes the shared-author-record bug ([#162](https://github.com/ata381/BibMedEd/issues/162))
- [ ] Affiliation completeness and country-attribution report ([#169](https://github.com/ata381/BibMedEd/issues/169)); depends on OpenAlex institution data ([#154](https://github.com/ata381/BibMedEd/issues/154))
- [ ] Record cap never silent ([#151](https://github.com/ata381/BibMedEd/issues/151)), then raised with a split-by-year planner ([#170](https://github.com/ata381/BibMedEd/issues/170))
- [ ] One real study with a collaborator, reported with BIBLIO, submitted where these papers are published ([#171](https://github.com/ata381/BibMedEd/issues/171)); owner decision
- [ ] Positioning: reporting compliance over open data, for health-professions education ([#172](https://github.com/ata381/BibMedEd/issues/172))
- [ ] JOSS resubmission once #171 yields a citation: six months of public history were met in September 2026, and `paper.md` now carries the State of the field, Software design, Research impact and AI usage sections the pre-review asked for

## Next (0.5.x → 1.0)

- [ ] Additional adapters: [Europe PMC #7](https://github.com/ata381/BibMedEd/issues/7), [arXiv #9](https://github.com/ata381/BibMedEd/issues/9), [DOAJ #10](https://github.com/ata381/BibMedEd/issues/10), [OpenCitations #11](https://github.com/ata381/BibMedEd/issues/11), [CORE #12](https://github.com/ata381/BibMedEd/issues/12), [BASE #13](https://github.com/ata381/BibMedEd/issues/13)
- [ ] [Frontend i18n + Turkish locale #16](https://github.com/ata381/BibMedEd/issues/16)
- [ ] Idempotent set-screening endpoint ([#121](https://github.com/ata381/BibMedEd/issues/121))
- [ ] Project sharing — read-only public project URLs
- [ ] Saved query alerts (cron re-runs notify on new matching records)
- [ ] Keyed adapters built on the required-key table: Dimensions ([#69](https://github.com/ata381/BibMedEd/issues/69)) and CORE ([#12](https://github.com/ata381/BibMedEd/issues/12))
- [ ] Accessibility: axe scans across dashboard tabs and read-only mode ([#89](https://github.com/ata381/BibMedEd/issues/89)), network-graph label overlap fix ([#95](https://github.com/ata381/BibMedEd/issues/95))
- [ ] Verify the one-click Render deploy wires the frontend to the public API URL ([#93](https://github.com/ata381/BibMedEd/issues/93))
- [ ] Prometheus metrics endpoint (`/api/metrics`) once a Grafana dashboard ships alongside
- [ ] Strategic-diagram (thematic quadrants) plot in the dashboard ([#92](https://github.com/ata381/BibMedEd/issues/92))

## Later (1.x+)

- [ ] Polished public demo deployment with a read-only seeded project (deferred; read-only mode and the local demo already shipped)
- [ ] Plugin marketplace for community adapters
- [ ] Dual-reviewer screening workflow (Covidence parity); deferred because Covidence and Rayyan already serve it
- [ ] Opt-in relevance ranking for screening with a bring-your-own key, every suggestion and the model version written to the log; no automated decisions (replaces the earlier PICO-extraction item: reviewers want assistance, not replacement, and journals now require AI-use disclosure)
- [ ] Institutional SSO for multi-user labs
- [ ] Hosted multi-tenant cloud tier (managed Postgres, pooled NCBI keys)
- [ ] R and Python SDKs for programmatic access to projects and analyses

## Won't do

- A built-in citation manager — Zotero and EndNote already do this well, and BibMedEd exports clean `.RIS`.
- A reference-PDF storage layer — keep BibMedEd focused on metadata-level bibliometrics.

## How to influence the roadmap

- Up-vote (👍 reaction) issues you care about — that's the primary signal for prioritisation.
- Open an [adapter request](.github/ISSUE_TEMPLATE/adapter_request.yml) or [feature request](.github/ISSUE_TEMPLATE/feature_request.yml).
- Send a PR. Implemented > requested.
