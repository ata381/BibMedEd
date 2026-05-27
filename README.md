<p align="center">
  <h1 align="center">BibMedEd</h1>
  <p align="center"><strong>Open-Source Bibliometric Analysis Platform for Medical Education</strong></p>
</p>

<p align="center">
  <a href="https://github.com/ata381/BibMedEd/actions/workflows/ci.yml"><img src="https://github.com/ata381/BibMedEd/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.12+-green.svg" alt="Python 3.12+"></a>
  <a href="https://docs.docker.com/compose/"><img src="https://img.shields.io/badge/Docker-Compose-2496ED.svg" alt="Docker"></a>
  <a href="https://ata381.github.io/BibMedEd/"><img src="https://img.shields.io/badge/Docs-MkDocs-526CFE.svg" alt="Documentation"></a>
  <a href="https://doi.org/10.5281/zenodo.20404321"><img src="https://zenodo.org/badge/DOI/10.5281/zenodo.20404321.svg" alt="DOI"></a>
  <a href="CITATION.cff"><img src="https://img.shields.io/badge/cite-CITATION.cff-yellow.svg" alt="Cite this software"></a>
  <a href="CONTRIBUTING.md"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs welcome"></a>
  <a href="https://github.com/ata381/BibMedEd/issues"><img src="https://img.shields.io/github/issues/ata381/BibMedEd" alt="GitHub issues"></a>
  <a href="https://github.com/ata381/BibMedEd/graphs/contributors"><img src="https://img.shields.io/github/contributors/ata381/BibMedEd" alt="Contributors"></a>
</p>

<p align="center">
  <a href="https://ata381.github.io/BibMedEd/why-bibmeded/">Why BibMedEd?</a> &bull;
  <a href="https://ata381.github.io/BibMedEd/case-study/">Case Study</a> &bull;
  <a href="https://ata381.github.io/BibMedEd/">Documentation</a> &bull;
  <a href="https://ata381.github.io/BibMedEd/deploy/">Self-Hosting</a> &bull;
  <a href="https://ata381.github.io/BibMedEd/adapters/">Write an Adapter</a> &bull;
  <a href="https://render.com/deploy?repo=https://github.com/ata381/BibMedEd">Deploy to Cloud</a> &bull;
  <a href="ROADMAP.md">Roadmap</a> &bull;
  <a href="CONTRIBUTING.md">Contribute</a>
</p>

---

> Systematic bibliometric reviews currently require stitching together PubMed search, Covidence, VOSviewer, CiteSpace, and Excel — four tools, manual deduplication, and a methodology section that's painful to reconstruct. **BibMedEd is one application that does all of it**, self-hosts with one command, and exports a citable PRISMA-ready methodology log of every step it took.
>
> New here? Read **[Why BibMedEd vs Covidence / VOSviewer / Bibliometrix](https://ata381.github.io/BibMedEd/why-bibmeded/)** for an honest capability comparison, or jump into the **[end-to-end case study](https://ata381.github.io/BibMedEd/case-study/)**.

## Features

- **Multi-database search** — PubMed and OpenAlex built-in, extensible to any source via plug-and-play adapters
- **Automated deduplication** — Cross-database dedup by DOI and PMID
- **Six analysis modules** — Publications, authors, countries, keywords, citations, journals
- **Interactive visualizations** — D3.js co-authorship and keyword co-occurrence network graphs
- **Reproducible methodology** — Every pipeline step logged, exportable as a citable `.txt` for your Methods section
- **Standard exports** — .RIS (Zotero/EndNote), .CSV (Excel/Sheets), methodology log
- **Self-hostable** — Single `docker compose up` on any lab server, no cloud account needed
- **Result cap** — Default 2,000 record limit with live progress bar during fetch

> **See it in action:** [UI Tour with screenshots and demo video](https://ata381.github.io/BibMedEd/#user-interface-tour)

## Architecture

```
┌─────────────────────┐     ┌─────────────────────┐     ┌──────────────┐
│  Frontend (Next.js)  │◄───►│  Backend (FastAPI)   │◄───►│  PostgreSQL  │
│                     │     │                     │     └──────────────┘
│  - Search UI        │     │  - REST API         │
│  - Dashboard        │     │  - Adapter Registry  │     ┌──────────────┐
│  - D3.js Networks   │     │  - Analysis Engine  │◄───►│    Redis     │
│  - Export Manager   │     │  - Export Service   │     └──────────────┘
└─────────────────────┘     └─────────────────────┘           │
                                                      ┌──────────────┐
                                                      │Celery Workers│
                                                      │- Search      │
                                                      │- Analysis    │
                                                      └──────────────┘
```

## Quick Start

```bash
git clone https://github.com/ata381/BibMedEd
cd BibMedEd/bibmeded
docker compose up
```

Open [http://localhost:3000](http://localhost:3000). That's it.

> **Optional:** Create a free [NCBI API key](https://www.ncbi.nlm.nih.gov/account/) and add it to `.env` as `BIBMEDED_PUBMED_API_KEY=your_key` for 10 req/s instead of 3 req/s.

See the full [Self-Hosting Guide](https://ata381.github.io/BibMedEd/deploy/) for configuration, reset, and dev setup.

## Deploy to Cloud

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/ata381/BibMedEd)

One click provisions PostgreSQL, Redis, FastAPI, Celery, and the Next.js frontend on Render.com's free tier.

## Write Your Own Adapter

Adding a new bibliographic database is a single Python file (~50 lines):

```python
from app.adapters.base import BaseSourceAdapter, RawRecord, SearchResponse

class ScopusAdapter(BaseSourceAdapter):
    name = "scopus"
    display_name = "Scopus"
    requires_api_key = True

    async def search(self, query, **kwargs) -> SearchResponse:
        # Hit Scopus API, return IDs + count
        ...

    async def fetch(self, ids) -> list[RawRecord]:
        # Map Scopus JSON to RawRecord
        ...
```

Drop it in `app/adapters/`, restart the worker, and it appears in the search UI automatically. The adapter registry handles discovery, and cross-database deduplication works via the `external_ids` field.

See the full [Writing Adapters](https://ata381.github.io/BibMedEd/adapters/) guide with `RawRecord` field reference and an annotated OpenAlex walkthrough.


## Community & Roadmap

Want to help shape BibMedEd?

- **Start contributing:** See [CONTRIBUTING.md](CONTRIBUTING.md)
- **Request or claim work:** [GitHub Issues](https://github.com/ata381/BibMedEd/issues)
- **Discuss major ideas in a PR:** [Pull Requests](https://github.com/ata381/BibMedEd/pulls)
- **Use in research and cite the project:** See [Citation](#citation)

If you are looking for a first task, open an issue titled **"Good first issue request"** and we will suggest one.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, D3.js, Tailwind CSS |
| Backend | FastAPI, SQLAlchemy 2.0, Pydantic |
| Workers | Celery with Redis broker |
| Database | PostgreSQL 16 |
| Analysis | NetworkX, scikit-learn, scipy |
| Deployment | Docker Compose, Render.com Blueprint |

## Citation

If you use BibMedEd in your research, please cite:

```bibtex
@software{bibmeded,
  title   = {BibMedEd: Bibliometric Analysis Platform for Medical Education},
  author  = {Akillioglu, Ata},
  year    = {2026},
  doi     = {10.5281/zenodo.20404321},
  url     = {https://doi.org/10.5281/zenodo.20404321},
  note    = {Concept DOI — resolves to latest version. For a specific release, see Zenodo.}
}
```

## Contributing

Contributions are warmly welcome. The fastest path to a merged PR is to write an adapter for a new data source — most take ~50 lines.

- **Read** the [Contributing Guide](CONTRIBUTING.md) for setup, code style, and PR flow.
- **Pick a starter task** from [`GOOD_FIRST_ISSUES.md`](GOOD_FIRST_ISSUES.md) — 10+ vetted adapter ideas waiting for an owner.
- **Report bugs or request features** with the [issue templates](.github/ISSUE_TEMPLATE/).
- **Improve docs** — PRs to `docs/` auto-deploy to GitHub Pages on merge.

By contributing you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). Security issues should be reported via the process in [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) — use it freely in academic and commercial projects.

## Star history

<a href="https://star-history.com/#ata381/BibMedEd&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=ata381/BibMedEd&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=ata381/BibMedEd&type=Date" />
    <img alt="Star history of ata381/BibMedEd" src="https://api.star-history.com/svg?repos=ata381/BibMedEd&type=Date" />
  </picture>
</a>
