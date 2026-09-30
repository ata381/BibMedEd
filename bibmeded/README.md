# BibMedEd

Open-source bibliometric analysis for medical education research. Search PubMed,
OpenAlex, Crossref, Semantic Scholar and Lens, deduplicate across sources, and
analyse publications, authors, countries and collaboration networks.

This package installs the `bibmeded` command line tool and the Python library.
The full web application (Next.js UI, API, task workers) is self-hosted with Docker.

## Install

```bash
pip install bibmeded            # CLI + library, no server dependencies
pip install "bibmeded[server]"  # adds FastAPI, Celery, Redis, Postgres driver
```

Requires Python 3.12 or newer.

## Usage

```bash
# Estimate how many records a query matches (no database or worker needed)
bibmeded search "machine learning" --source openalex --dry-run
```

Fetching and storing records (`bibmeded search` without `--dry-run`) needs the
task worker stack: install the `server` extra and run Redis, a database and a
Celery worker, or simply use `docker compose up` from the repository.

## Links

- Documentation: https://ata381.github.io/BibMedEd/
- Source and issues: https://github.com/ata381/BibMedEd
- Changelog: https://github.com/ata381/BibMedEd/blob/master/CHANGELOG.md

Licensed under MIT.
