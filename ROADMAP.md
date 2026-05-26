# BibMedEd Roadmap

A living document. Items move up and down as the community contributes adapters and bug reports.

## Now (0.x)

- [x] PubMed + OpenAlex adapters with cross-source DOI / PMID deduplication
- [x] Six analysis modules (publications, authors, countries, keywords, citations, journals)
- [x] D3.js co-authorship and keyword co-occurrence networks
- [x] Methodology export as a citable `.txt` file
- [x] One-click Render.com deploy
- [x] Continuous integration on every PR (Python 3.12 / 3.13, frontend build, Docker build)
- [ ] Polished public demo deployment with seeded sample project
- [ ] CITATION.cff + JOSS submission (in flight — see `paper.md`)

## Next (0.x → 1.0)

- [ ] Additional adapters: CrossRef, Europe PMC, Semantic Scholar, arXiv, Scopus, Web of Science, Dimensions, CORE, BASE, Lens.org
- [ ] PRISMA flow diagram export
- [ ] Project sharing — read-only public project URLs
- [ ] Saved query alerts (cron re-runs notify on new matching records)
- [ ] Author disambiguation using ORCID + co-author network
- [ ] LLM-assisted PICO extraction and abstract screening (opt-in, bring-your-own key)

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
