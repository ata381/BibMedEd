# Scripting BibMedEd

BibMedEd is primarily a self-hosted web app, but every UI action is also a REST endpoint.
This page is for researchers who want to drive the tool from a Jupyter notebook, batch over
many topic queries, or pull deduplicated data into a pandas / polars pipeline.

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

Upstream APIs (PubMed E-utilities, OpenAlex, CrossRef, Semantic Scholar) have their own
rate limits. BibMedEd respects each adapter's documented courtesy patterns
(`mailto=` for OpenAlex / CrossRef, `api_key` for PubMed and Semantic Scholar). Set these
in `bibmeded/.env` before starting the worker:

```dotenv
BIBMEDED_PUBMED_API_KEY=...
BIBMEDED_NCBI_EMAIL=you@example.com
BIBMEDED_OPENALEX_EMAIL=you@example.com
BIBMEDED_CROSSREF_EMAIL=you@example.com
BIBMEDED_SEMANTIC_SCHOLAR_API_KEY=...
```

The Celery soft time limit is 600 seconds per task — for very large windowed searches you
may want to split by year range and merge.

## Methodology export from scripts

`GET /api/projects/{id}/export/methodology` returns the citable PRISMA-aligned text log.
`GET /api/projects/{id}/export/prisma` returns the SVG. Both reflect manual exclusions
made through the toggle / bulk-exclude endpoints, so a fully programmatic workflow can
still produce a journal-quality methodology section.
