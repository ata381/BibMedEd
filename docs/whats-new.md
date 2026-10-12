# BibMedEd 0.4: install from PyPI, a redesigned interface, and a read-only demo mode

BibMedEd 0.4.0, released on 2026-09-30, is the first version published to PyPI. It also brings a redesigned frontend, a read-only mode for showing a seeded project safely, and two CLI commands from first-time contributors. One change is breaking: the Python import package was renamed from `app` to `bibmeded`.

## Install the CLI from PyPI

`pip install bibmeded` now installs a lightweight command-line tool, with no Docker and no web UI ([#84](https://github.com/ata381/BibMedEd/pull/84)):

```bash
python -m venv .venv && source .venv/bin/activate   # Python 3.12 or newer
pip install bibmeded

bibmeded --version
bibmeded sources
bibmeded search "medical education" --source openalex --dry-run
```

The base install covers `--version`, `sources` and `search --dry-run`. Fetching and storing records still runs through the Celery pipeline, so a full `bibmeded search` needs the `server` extra (`pip install "bibmeded[server]"`) plus Redis and a database, or the Docker stack. See [Scripting & API](scripting.md).

Two of these commands are community contributions:

- `bibmeded --version` prints the installed version ([#72](https://github.com/ata381/BibMedEd/pull/72), by [@Sandro850](https://github.com/Sandro850)).
- `bibmeded sources` lists the registered adapters and whether each one's API key is configured; add `--json` for machine-readable output ([#71](https://github.com/ata381/BibMedEd/pull/71), by [@DYNOSuprovo](https://github.com/DYNOSuprovo)). Key values are never printed.

## Breaking: the import package is now `bibmeded`

The Python package was renamed from `app` to `bibmeded`, so the wheel no longer installs a generic top-level `app` package ([#97](https://github.com/ata381/BibMedEd/pull/97)). If you run BibMedEd outside the provided Docker Compose files, update your commands:

```bash
uvicorn bibmeded.main:app
celery -A bibmeded.workers.celery_app worker
```

Celery task names are now `bibmeded.workers.tasks.*`. Drain queued tasks before you upgrade, because tasks queued under the old names will not be picked up.

## A redesigned interface

The frontend has a new journal-editorial look, and the redesign includes WCAG 2.2 accessibility fixes ([#75](https://github.com/ata381/BibMedEd/pull/75)). The screenshots on the [home page](index.md#user-interface-tour) show the new interface with the bundled sample corpus.

## Show a project without letting anyone change it

Setting `BIBMEDED_READ_ONLY=true` rejects every mutating request with `403` and shows a read-only banner in the UI ([#81](https://github.com/ata381/BibMedEd/pull/81)). Visitors can browse a seeded project, its analyses and its exports, but cannot create, delete, search or exclude.

You can try this mode locally with one command, with no Postgres, Redis or worker ([#86](https://github.com/ata381/BibMedEd/pull/86)):

```bash
cd bibmeded
docker compose -f docker-compose.demo.yml up --build
```

Then open <http://localhost:3100>. The same release ships a free-plan Render Blueprint, `deploy/render-demo.yaml`, for hosting your own demo. The project does not run a hosted public demo yet; that is deliberately deferred. Read [Public read-only demo](deploy.md#public-read-only-demo) before exposing an instance, since everything in a read-only instance's database is publicly readable.

## Fresh installs work on SQLAlchemy 2.1

SQLAlchemy 2.1 changed the default driver for bare `postgresql://` URLs to psycopg v3, so fresh installs failed with `ModuleNotFoundError: No module named 'psycopg'`. `BIBMEDED_DATABASE_URL` values of `postgres://` or `postgresql://` are now normalised to `postgresql+psycopg2://` ([#76](https://github.com/ata381/BibMedEd/pull/76)). URLs that name a driver, and non-Postgres URLs, are left as they are.

## Try it or help shape it

- Follow the [quick start](index.md#quick-start) and choose **Explore sample project**.
- Read the [end-to-end case study](case-study.md).
- Share a real workflow or question in [GitHub Discussions](https://github.com/ata381/BibMedEd/discussions).
- Claim a focused task from the [good first contributions list](https://github.com/ata381/BibMedEd/blob/master/GOOD_FIRST_ISSUES.md).

The full list of changes in 0.4.0, and in every earlier release, is in the [CHANGELOG](https://github.com/ata381/BibMedEd/blob/master/CHANGELOG.md).

BibMedEd remains a single-tenant, self-hosted tool without built-in authentication. Do not expose a writable deployment directly to the public internet; review the [security model](deploy.md#security-model) first.
