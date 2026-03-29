# BibMedEd

**Bibliometric Analysis Platform for Medical Education**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-green.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docs.docker.com/compose/)

BibMedEd is an open-source tool that enables medical education researchers to search bibliographic databases and perform comprehensive bibliometric analysis. It replaces the fragmented workflow of PubMed + Covidence + VOSviewer + CiteSpace + Excel with a single integrated platform.

## Features

- **Multi-database search** — PubMed and OpenAlex built-in, extensible to any source via adapters
- **Automated deduplication** — Cross-database dedup by DOI and PMID
- **Six analysis modules** — Publications, authors, countries, keywords, citations, journals
- **Interactive visualizations** — D3.js co-authorship and keyword co-occurrence networks
- **Reproducible methodology** — Every pipeline step logged, exportable as a citable `.txt` file
- **Standard exports** — .RIS (Zotero/EndNote), .CSV (Excel/Sheets)

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
                                                      └──────────────┘
```

## Quick Start

```bash
git clone https://github.com/ata381/bibmeded
cd bibmeded/bibmeded
docker compose up
```

Open [http://localhost:3000](http://localhost:3000).

See the [Self-Hosting Guide](https://ata381.github.io/bibmeded/deploy/) for configuration options.

## Deploy to Cloud

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/ata381/bibmeded)

One click provisions PostgreSQL, Redis, FastAPI, Celery, and the Next.js frontend on Render.com's free tier.

## Write Your Own Adapter

Adding a new data source is a single Python file:

```python
from app.adapters.base import BaseSourceAdapter, RawRecord, SearchResponse

class MySourceAdapter(BaseSourceAdapter):
    name = "mysource"
    display_name = "My Source"
    requires_api_key = False

    async def search(self, query, **kwargs) -> SearchResponse: ...
    async def fetch(self, ids) -> list[RawRecord]: ...
```

Drop it in `app/adapters/`, restart, and it appears in the UI. See the full [Writing Adapters](https://ata381.github.io/bibmeded/adapters/) guide.

## Citation

```bibtex
@software{bibmeded,
  title={BibMedEd: Bibliometric Analysis Platform for Medical Education},
  author={Ata, Aakil},
  year={2026},
  url={https://github.com/ata381/bibmeded}
}
```

## Contributing

Contributions welcome! The easiest way to contribute is writing an adapter for a new data source. See the [adapter guide](https://ata381.github.io/bibmeded/adapters/) for the full walkthrough.

Bug reports and feature requests: [open an issue](https://github.com/ata381/bibmeded/issues).

## License

[MIT](LICENSE)
