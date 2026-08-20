# BibMedEd Roadmap

A living document. Items move up and down as the community contributes adapters and bug reports.

## Now (0.2.0 — shipped 2026-05-28)

- [x] Four adapters: PubMed, OpenAlex, CrossRef, Semantic Scholar — with cross-source DOI / PMID deduplication
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

## Next (0.2.x → 1.0)

- [ ] Additional adapters: [Europe PMC #7](https://github.com/ata381/BibMedEd/issues/7), [arXiv #9](https://github.com/ata381/BibMedEd/issues/9), [DOAJ #10](https://github.com/ata381/BibMedEd/issues/10), [OpenCitations #11](https://github.com/ata381/BibMedEd/issues/11), [CORE #12](https://github.com/ata381/BibMedEd/issues/12), [BASE #13](https://github.com/ata381/BibMedEd/issues/13), [Lens.org #14](https://github.com/ata381/BibMedEd/issues/14)
- [ ] [Frontend i18n + Turkish locale #16](https://github.com/ata381/BibMedEd/issues/16)
- [x] [Search CLI `--dry-run` for cost estimation #17](https://github.com/ata381/BibMedEd/issues/17)
- [ ] Title/abstract vs full-text screening-stage distinction (PRISMA 2020 splits these; currently one binary excluded flag)
- [ ] Project sharing — read-only public project URLs
- [ ] Saved query alerts (cron re-runs notify on new matching records)
- [ ] Author disambiguation using ORCID + co-author network
- [ ] Dual-reviewer screening workflow (Covidence parity)
- [ ] Prometheus metrics endpoint (`/api/metrics`) once a Grafana dashboard ships alongside
- [ ] Strategic-diagram (thematic quadrants) plot in the dashboard
- [ ] LLM-assisted PICO extraction and abstract screening (opt-in, bring-your-own key)
- [x] Bundled synthetic sample project for network-free first-run exploration
- [ ] Polished public demo deployment with a read-only seeded project
- [ ] JOSS submission (paper.md and paper.bib are ready as of v0.2.0)

## Later (1.x+)

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
