<p align="center">
  <h1 align="center">BibMedEd</h1>
  <p align="center"><strong>Open-Source Bibliometric Analysis Platform for Medical Education</strong></p>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.12+-green.svg" alt="Python 3.12+"></a>
  <a href="https://docs.docker.com/compose/"><img src="https://img.shields.io/badge/Docker-Compose-2496ED.svg" alt="Docker"></a>
  <a href="https://ata381.github.io/Tip-egitimi-entegrasyon/"><img src="https://img.shields.io/badge/Docs-MkDocs-526CFE.svg" alt="Documentation"></a>
</p>

<p align="center">
  <a href="https://ata381.github.io/Tip-egitimi-entegrasyon/">Documentation</a> &bull;
  <a href="https://ata381.github.io/Tip-egitimi-entegrasyon/deploy/">Self-Hosting</a> &bull;
  <a href="https://ata381.github.io/Tip-egitimi-entegrasyon/adapters/">Write an Adapter</a> &bull;
  <a href="https://render.com/deploy?repo=https://github.com/ata381/Tip-egitimi-entegrasyon">Deploy to Cloud</a>
</p>

---

BibMedEd replaces the fragmented workflow of PubMed + Covidence + VOSviewer + CiteSpace + Excel with a single integrated platform. Search multiple bibliographic databases, analyze trends, visualize research networks, and export reproducible methodology logs — all from one tool.

## Features

- **Multi-database search** — PubMed and OpenAlex built-in, extensible to any source via plug-and-play adapters
- **Automated deduplication** — Cross-database dedup by DOI and PMID
- **Six analysis modules** — Publications, authors, countries, keywords, citations, journals
- **Interactive visualizations** — D3.js co-authorship and keyword co-occurrence network graphs
- **Reproducible methodology** — Every pipeline step logged, exportable as a citable `.txt` for your Methods section
- **Standard exports** — .RIS (Zotero/EndNote), .CSV (Excel/Sheets), methodology log
- **Self-hostable** — Single `docker compose up` on any lab server, no cloud account needed
- **Result cap** — Default 2,000 record limit with live progress bar during fetch

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
git clone https://github.com/ata381/Tip-egitimi-entegrasyon
cd Tip-egitimi-entegrasyon/bibmeded
docker compose up
```

Open [http://localhost:3000](http://localhost:3000). That's it.

> **Optional:** Create a free [NCBI API key](https://www.ncbi.nlm.nih.gov/account/) and add it to `.env` as `BIBMEDED_PUBMED_API_KEY=your_key` for 10 req/s instead of 3 req/s.

See the full [Self-Hosting Guide](https://ata381.github.io/Tip-egitimi-entegrasyon/deploy/) for configuration, reset, and dev setup.

## Deploy to Cloud

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/ata381/Tip-egitimi-entegrasyon)

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

See the full [Writing Adapters](https://ata381.github.io/Tip-egitimi-entegrasyon/adapters/) guide with `RawRecord` field reference and an annotated OpenAlex walkthrough.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, D3.js, Tailwind CSS |
| Backend | FastAPI, SQLAlchemy 2.0, Pydantic |
| Workers | Celery with Redis broker |
| Database | PostgreSQL 16 |
| Analysis | NetworkX, pandas, scikit-learn, scipy |
| Deployment | Docker Compose, Render.com Blueprint |

## Citation

If you use BibMedEd in your research, please cite:

```bibtex
@software{bibmeded,
  title={BibMedEd: Bibliometric Analysis Platform for Medical Education},
  author={Ata, Aakil},
  year={2026},
  url={https://github.com/ata381/Tip-egitimi-entegrasyon}
}
```

## Contributing

Contributions welcome! The easiest way to start:

1. **Write an adapter** for a new data source — see the [adapter guide](https://ata381.github.io/Tip-egitimi-entegrasyon/adapters/)
2. **Report bugs** or request features — [open an issue](https://github.com/ata381/Tip-egitimi-entegrasyon/issues)
3. **Improve docs** — PRs to `docs/` are auto-deployed to GitHub Pages

## License

[MIT](LICENSE) — use it freely in academic and commercial projects.
