# Scripting BibMedEd

BibMedEd is primarily a self-hosted web app, but every UI action is also a REST endpoint.
This page is for researchers who want to drive the tool from a Jupyter notebook, batch over
many topic queries, or pull deduplicated data into a pandas / polars pipeline.

## List available sources from the CLI

Inspect registered bibliographic adapters and whether their API keys are configured:

```bash
bibmeded sources
bibmeded sources --json
```

Each JSON entry reports `api_key_requirement` as `required`, `optional`, or `no`; key values are never printed:

```json
{"name": "lens", "display_name": "Lens.org", "api_key_requirement": "required", "status": "missing BIBMEDED_LENS_API_KEY"}
```

## Install from PyPI (CLI only)

If you only want the command line tool (no Docker, no web UI), install it with `pipx install bibmeded` or into a dedicated virtual environment (recommended, to keep its dependencies isolated):

```bash
python -m venv .venv && source .venv/bin/activate   # Python 3.12 or newer
pip install bibmeded
bibmeded search "medical education" --source openalex --dry-run
```

The base install is lightweight and supports `--dry-run` result estimates. Fetching and storing records
(`bibmeded search` without `--dry-run`) goes through the Celery pipeline, so it additionally needs the
`server` extra plus Redis and a database, or simply the Docker stack:

```bash
pip install "bibmeded[server]"
```

## Estimate search results from the CLI

Before fetching a large result set, use `--dry-run` to estimate how many records a query will return:

```bash
bibmeded search "machine learning" --dry-run
```

## OpenAPI surface

When the API is running locally:

- **Interactive Swagger UI**: <http://localhost:8000/docs>
- **ReDoc**: <http://localhost:8000/redoc>
- **Raw OpenAPI 3.1 spec**: <http://localhost:8000/openapi.json>

Use the raw spec with [`openapi-generator`](https://openapi-generator.tech/) to generate a
typed client in Python, TypeScript, R, or any other supported language.

## Versioning contract

Every analysis response carries a `schema_version` field. As of v0.2.0 the version is
`"1.0"`. Additive changes (new optional keys on existing endpoints) do not bump the version;
breaking changes do. Pin against this field in any downstream pipeline you build.

## Minimal Python example (httpx)

No code generation needed for simple scripting — the raw API is small enough:

```python
import httpx

API = "http://localhost:8000"
with httpx.Client(base_url=API, timeout=60) as c:
    # 1. Create a project
    project = c.post("/api/projects", json={"name": "AI in MedEd 2024"}).json()
    pid = project["id"]

    # 2. Trigger a search
    c.post(f"/api/projects/{pid}/search", json={
        "query_string": '(Artificial Intelligence[Mesh]) AND (Education, Medical[Mesh])',
        "source": "pubmed",
        "year_start": "2020",
        "year_end": "2024",
        "max_results": 2000,
    })

    # 3. Poll until completed
    import time
    while True:
        status = c.get(f"/api/projects/{pid}/search/latest").json()
        if status["status"] in {"completed", "failed"}:
            break
        time.sleep(2)

    # 4. Run an analysis
    authors = c.post(f"/api/projects/{pid}/analysis/authors").json()
    print(authors["results"]["schema_version"])  # "1.0"
    print(authors["results"]["top_authors"][:5])

    # 5. Pull the deduplicated dataset as versioned JSON
    payload = c.get(f"/api/projects/{pid}/export/json").json()
    print(f"{payload['count']} publications, schema_version={payload['schema_version']}")
```

## Bulk export for downstream ML

The `/api/projects/{id}/export/json` endpoint returns a single JSON object with a stable
publication schema (`pmid`, `doi`, `title`, `abstract`, `year`, `authors`, `keywords`,
`citation_count`, `excluded`, `exclusion_reason`, etc.). For pandas:

```python
import pandas as pd
import httpx

resp = httpx.get(f"http://localhost:8000/api/projects/{pid}/export/json")
payload = resp.json()
df = pd.json_normalize(payload["publications"])
df.to_parquet("corpus.parquet")
```

For the full submission bundle (CSV + RIS + JSON + methodology + PRISMA SVG + manifest in
one .zip), hit `/api/projects/{id}/export/bundle`.

## Batch over many queries

Searches are dispatched to Celery and return HTTP 202 immediately. To batch 50 queries:

```python
import asyncio, httpx

async def run_one(c, topic):
    project = (await c.post("/api/projects", json={"name": topic})).json()
    await c.post(f"/api/projects/{project['id']}/search", json={
        "query_string": topic, "source": "pubmed", "max_results": 500,
    })
    return project["id"]

async def main(topics):
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=60) as c:
        return await asyncio.gather(*[run_one(c, t) for t in topics])
```

Polling cadence is up to you. The status endpoint at
`GET /api/projects/{id}/search/latest` is cheap.

## Rate limits and politeness

Upstream APIs (PubMed E-utilities, OpenAlex, CrossRef, Semantic Scholar, Lens.org) have their own
rate limits. BibMedEd respects each adapter's documented courtesy patterns
(`mailto=` for OpenAlex / CrossRef, `api_key` for PubMed, Semantic Scholar, and Lens.org). Set these
in `bibmeded/.env` before starting the worker:

```dotenv
BIBMEDED_PUBMED_API_KEY=...
BIBMEDED_NCBI_EMAIL=you@example.com
BIBMEDED_OPENALEX_EMAIL=you@example.com
BIBMEDED_CROSSREF_EMAIL=you@example.com
BIBMEDED_SEMANTIC_SCHOLAR_API_KEY=...
BIBMEDED_LENS_API_KEY=...
```

The Celery soft time limit is 600 seconds per task — for very large windowed searches you
may want to split by year range and merge.

## Methodology export from scripts

`GET /api/projects/{id}/export/methodology` returns the citable PRISMA-aligned text log.
`GET /api/projects/{id}/export/prisma` returns the SVG. Both reflect manual exclusions
made through the toggle / bulk-exclude endpoints, so a fully programmatic workflow can
still produce a journal-quality methodology section.

## Screening stages

PRISMA 2020 reports screening in two stages: title/abstract screening of *records* and
full-text assessment of *reports*. Every exclusion carries a `screening_stage`:

| Value | PRISMA 2020 box |
|---|---|
| `title_abstract` | Records excluded (beside "Records screened") |
| `full_text` | Reports excluded, or Reports not retrieved when the reason is `fulltext_unavailable` |

Both exclude endpoints accept an optional `screening_stage`. When it is omitted the stage is
`title_abstract`, so clients written before stages existed keep their old meaning.

```python
# Exclude a record at full-text assessment
c.patch(f"/api/projects/{pid}/publications/{pub_id}/exclude",
        json={"reason": "wrong_outcome", "screening_stage": "full_text"})
# -> {"id": ..., "excluded": true, "exclusion_reason": "wrong_outcome", "screening_stage": "full_text"}

# Bulk-exclude low-citation records (stage defaults to title_abstract)
c.post(f"/api/projects/{pid}/publications/bulk-exclude", json={"citation_threshold": 0})
# -> {"excluded_count": ..., "reason": "other", "screening_stage": "title_abstract"}
```

The endpoint is a toggle: calling it on an excluded record re-includes it and clears both
`exclusion_reason` and `screening_stage`, whatever the body says. A record has one stage,
the stage it was excluded at; to move an exclusion to the other stage, re-include it and
exclude it again. `GET /api/projects/{id}/publications` and the JSON export return
`screening_stage` on every publication (`null` while it is included).

The flow diagram counts *reports sought for retrieval* as records screened minus
title/abstract exclusions, and *reports assessed for eligibility* as reports sought minus
reports not retrieved. The methodology log lists both stages with per-reason counts.
Alembic revision `0004_screening_stage` migrates existing exclusions to `title_abstract`; if any excluded record still
has no stage, both exports count it at title/abstract and say how many there are.

These are additive response fields, so `schema_version` stays `"1.0"`.
