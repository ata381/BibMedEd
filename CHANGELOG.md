# Changelog

All notable changes to BibMedEd are recorded here. This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Frontend design system overhaul.** `bibmeded/frontend/src/app/globals.css` is now a real design-token foundation (semantic color tokens for light + dark, full type/spacing/radius/motion scales, focus-ring + reduced-motion respect, print styles) wired into Tailwind 4 via `@theme inline`. Six accessible primitives under `bibmeded/frontend/src/components/ui/` — `Button`, `Card`, `Tabs`, `Badge`, `Skeleton`, `EmptyState` — plus a no-flash `ThemeToggle` with system/light/dark choice. Sidebar gains `aria-current`, `aria-label`s, visible focus rings, a project-section header, and quick GitHub/docs/theme controls. Export page rebuilt to use the new system as the reference implementation (proper tabs widget with arrow-key nav, segmented format radio, bundled-download row, skeleton loading states, semantic colour usage throughout). `design-system/bibmeded/MASTER.md` captured for future-session reference.
- **PRISMA 2020 flow-diagram export** (`GET /api/projects/{id}/export/prisma`). Closes [#15](https://github.com/ata381/BibMedEd/issues/15). Pure-Python SVG renderer that derives identified / removed-before-screening / screened / excluded / included counts directly from the methodology log; per-source breakdown in the identification box. Exposed in the frontend Export page next to the methodology log download with an inline live preview.
- **CrossRef adapter** (`app/adapters/crossref.py`). Authoritative DOI metadata source — closes [#6](https://github.com/ata381/BibMedEd/issues/6). Adds significant cross-source deduplication leverage because most other adapters carry a DOI but few normalise it; CrossRef hands you the canonical lowercase form. Polite-pool `mailto`, cursor pagination, references list, year-extraction fallback chain.
- ESLint flat-config wired into the frontend CI; closes [#25](https://github.com/ata381/BibMedEd/issues/25). React 19 Compiler warnings tracked in [#26](https://github.com/ata381/BibMedEd/issues/26).
- `tsc --noEmit` is strict in CI (was silently swallowing errors).
- Branch protection on `master` requiring all 5 CI checks, linear history, conversation resolution.
- Dependabot (pip + npm + actions, weekly), CodeQL (Python + TypeScript), JOSS draft-pdf workflow on every paper change.

### Planned
- Adapters: Europe PMC, Semantic Scholar, arXiv, DOAJ, OpenCitations, CORE, BASE, Lens.org — see [`GOOD_FIRST_ISSUES.md`](GOOD_FIRST_ISSUES.md).
- PRISMA flow-diagram PNG/SVG export ([#15](https://github.com/ata381/BibMedEd/issues/15)).
- i18n scaffold + Turkish locale ([#16](https://github.com/ata381/BibMedEd/issues/16)).
- Search CLI `--dry-run` for cost estimation ([#17](https://github.com/ata381/BibMedEd/issues/17)).

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

[Unreleased]: https://github.com/ata381/BibMedEd/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/ata381/BibMedEd/releases/tag/v0.1.2
[0.1.1]: https://github.com/ata381/BibMedEd/releases/tag/v0.1.1
[0.1.0]: https://github.com/ata381/BibMedEd/releases/tag/v0.1.0
