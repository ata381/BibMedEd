# BibMedEd Roadmap

A living document. Items move up and down as the community contributes adapters and bug reports.

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

## Next (0.4.x → 1.0)

- [ ] Additional adapters: [Europe PMC #7](https://github.com/ata381/BibMedEd/issues/7), [arXiv #9](https://github.com/ata381/BibMedEd/issues/9), [DOAJ #10](https://github.com/ata381/BibMedEd/issues/10), [OpenCitations #11](https://github.com/ata381/BibMedEd/issues/11), [CORE #12](https://github.com/ata381/BibMedEd/issues/12), [BASE #13](https://github.com/ata381/BibMedEd/issues/13)
- [ ] [Frontend i18n + Turkish locale #16](https://github.com/ata381/BibMedEd/issues/16)
- [ ] Title/abstract vs full-text screening-stage distinction ([#91](https://github.com/ata381/BibMedEd/issues/91); PRISMA 2020 splits these, currently one binary excluded flag)
- [ ] Project sharing — read-only public project URLs
- [ ] Saved query alerts (cron re-runs notify on new matching records)
- [ ] Author disambiguation using ORCID + co-author network
- [ ] Dual-reviewer screening workflow (Covidence parity)
- [ ] Table-driven required-key adapter configuration ([#88](https://github.com/ata381/BibMedEd/issues/88)), unblocking keyed adapters such as Dimensions ([#69](https://github.com/ata381/BibMedEd/issues/69)) and CORE ([#12](https://github.com/ata381/BibMedEd/issues/12))
- [ ] Accessibility: axe scans across dashboard tabs and read-only mode ([#89](https://github.com/ata381/BibMedEd/issues/89)), accessible ConfirmDialog ([#90](https://github.com/ata381/BibMedEd/issues/90)), network-graph label overlap fix ([#95](https://github.com/ata381/BibMedEd/issues/95))
- [ ] Sample project ships a stored search query ([#94](https://github.com/ata381/BibMedEd/issues/94))
- [ ] Verify the one-click Render deploy wires the frontend to the public API URL ([#93](https://github.com/ata381/BibMedEd/issues/93))
- [ ] Engineering hygiene: e2e mock contract check ([#78](https://github.com/ata381/BibMedEd/issues/78)), persist-loop SAWarning ([#87](https://github.com/ata381/BibMedEd/issues/87)), `request_id_ctx` import cycle ([#98](https://github.com/ata381/BibMedEd/issues/98))
- [ ] Prometheus metrics endpoint (`/api/metrics`) once a Grafana dashboard ships alongside
- [ ] Strategic-diagram (thematic quadrants) plot in the dashboard ([#92](https://github.com/ata381/BibMedEd/issues/92))
- [ ] LLM-assisted PICO extraction and abstract screening (opt-in, bring-your-own key)
- [ ] JOSS readiness (not yet submitted): remaining blockers are at least one independent research use case and an explicit AI-usage disclosure in `paper.md`; six months of public development history and current paper metadata are also required

## Later (1.x+)

- [ ] Polished public demo deployment with a read-only seeded project (deferred; read-only mode and the local demo already shipped)
- [ ] Plugin marketplace for community adapters
- [ ] Dual-reviewer screening workflow (Covidence parity)
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
