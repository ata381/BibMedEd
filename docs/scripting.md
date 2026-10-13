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

For the full submission bundle (CSV + RIS + Web of Science plain text + JSON + methodology +
PRISMA SVG + screening decision log CSV + manifest in one .zip), hit
`/api/projects/{id}/export/bundle`.

## Web of Science plain text for VOSviewer and Bibliometrix

`GET /api/projects/{id}/export/wos` returns the included records in the Web of Science
tagged plain-text format (`.txt`, UTF-8 with a byte-order mark, as Clarivate writes it).
This is the format VOSviewer reads under *Create map → Read data from bibliographic
database files → Web of Science*, and the one Bibliometrix reads with:

```r
library(bibliometrix)
M <- convert2df("project-wos-2026-10-12.txt", dbsource = "wos", format = "plaintext")
```

The file opens with `FN Clarivate Analytics Web of Science` and `VR 1.0`. Each record starts
with `PT J` and ends with `ER` and a blank line, and the file ends with `EF`. A field with
several values (authors, addresses, cited references) puts one value per line, with
continuation lines indented by three spaces. A field BibMedEd has no value for is left out,
never written empty. Line breaks inside values are replaced by spaces, so a value cannot
start a new tag or record.

| Tag | Content | Source in BibMedEd |
|---|---|---|
| `PT` | Publication type, always `J` | constant |
| `AU` | One author per line, `Surname, Initials` | author name |
| `AF` | One author per line, `Surname, Given names` | author name |
| `TI` | Title | title |
| `SO` | Source title | journal name |
| `DT` | Document type | publication type, as the source gave it |
| `DE` | Author keywords, separated by `; ` | keywords the source supplied (not MeSH) |
| `ID` | MeSH terms, separated by `; ` | MeSH terms |
| `AB` | Abstract | abstract |
| `C1` | One address per line, `[Authors] Affiliation, Country.` | author affiliations (see below) |
| `CR` | One cited reference per line, `SURNAME I, YEAR, SOURCE, DOI <doi>` or `DOI <doi>` | reference list (see below) |
| `NR` | Number of references the source reported | reference list |
| `TC` | Times cited | citation count |
| `SN`, `EI` | ISSN, eISSN | journal |
| `PY` | Publication year | year |
| `DI` | DOI | DOI |
| `UT` | Unique record id, `<SOURCE>:<id>` such as `PUBMED:31234567` or `OPENALEX:W2741809807` | source and source-native id |
| `PM` | PubMed ID, PubMed records only | PMID |

Known gaps:

- **Cited references.** BibMedEd stores each record's references as identifiers, not as
  the `Author, Year, Source, Volume, Page, DOI` strings Web of Science writes. A reference
  that resolves to a record in the same export, by DOI or by source-native id (an OpenAlex
  ID, a Lens ID, a PMID) using the same matching as the citation analysis, is written in WoS
  cited-reference form from that record: first-author surname and initials, year and journal
  name, all upper case, then the DOI, for example
  `DEMIR SA, 2019, MEDICAL EDUCATION, DOI 10.1111/medu.13900`. Parts the cited record lacks are
  left out. Any other reference that is a DOI is written as bare `DOI <doi>`, because BibMedEd
  holds nothing else about it. References that are neither are left out of `CR`; `NR` still
  gives the full count, and the bundle's `MANIFEST.txt` states how many of the references
  reached `CR`. PubMed does not return reference lists, so PubMed records have no `CR` or `NR`.
- **What this means in each tool.** Bibliometrix's local-citation analysis (`histNetwork`,
  `localCitations`) matches a `CR` entry against each record's first author, year and source
  plus its DOI, so it counts citations between records of the same export and nothing else;
  a bare `DOI <doi>` never matches. VOSviewer's co-citation maps of cited sources and cited
  authors read the source and author out of each `CR` entry, so they are only populated by
  the full-form, in-corpus references; bare `DOI <doi>` entries contribute neither. Both
  tools see a citation network limited to the exported corpus.
- **Author names.** PubMed names arrive as `Surname, Given`; a PubMed author without a comma
  is a collective author and is written unchanged. Other sources give `Given Surname`, and
  the last word is taken as the surname. Surnames with particles (`van der Berg`) and
  organisation names from those sources are split at the last word too.
- **Addresses.** Affiliations belong to an author record, not to a paper, and author
  records are shared across the whole database by normalised name (all projects, all
  sources). `C1` therefore lists every affiliation BibMedEd holds for that name, which can
  include affiliations seen on other papers, or on another person with the same normalised
  name. Each address is the stored affiliation text; when the text does not already end with
  the stored country (aliases such as `England` for `UK` count as ending with it), the
  country is appended, because VOSviewer takes the last comma-separated part as the country.
  Every address ends with a period, because Bibliometrix splits addresses and matches
  countries on it.
- **`ID` holds MeSH terms**, not Clarivate's KeyWords Plus, and `UT` is not a Web of Science
  accession number. Bibliometrix reads both as plain text, so analyses run, but
  results labelled "Keywords Plus" are MeSH-based.
- **Not exported:** language, volume, issue, pages, funding, reprint address, research
  areas and cited-reference details, because BibMedEd does not store them.

## CSV export columns

The CSV export contains these columns in order:

| Column | Meaning |
|---|---|
| `PMID` | PubMed identifier, when available |
| `DOI` | DOI, when available |
| `Title` | Publication title |
| `Authors` | Authors separated by `; ` |
| `Journal` | Journal name |
| `Year` | Publication year |
| `Citations` | Recorded citation count; empty when no count is available, while `0` means a recorded zero |
| `Keywords` | Keywords separated by `; ` |
| `Abstract` | Abstract text, with line breaks flattened to spaces |

The empty `Citations` cell intentionally preserves the difference between missing data and
a measured zero; downstream Excel, R, and pandas workflows should not coerce it to `0`.

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

`docker compose up` passes these into the `api` and `worker` containers. PubMed requests run at
10 per second when `BIBMEDED_PUBMED_API_KEY` is set and 3 per second otherwise;
`BIBMEDED_PUBMED_RATE_LIMIT` overrides both. The rate used is recorded in the search step of the
methodology log.

The Celery soft time limit is 600 seconds per task — for very large windowed searches you
may want to split by year range and merge.

## Author productivity (Lotka's law)

The authors analysis ranks authors by the h-index (Hirsch 2005), g-index (Egghe 2006) and
e-index (Zhang 2009), all computed within the project's corpus. Its `lotka` block fits
Lotka's law (Lotka 1926): the number of authors with *n* papers is about C / n^alpha,
with alpha close to 2 in many fields.

- `distribution` lists every productivity level (`papers`, `authors`). Authors are counted
  in full on every included paper they co-wrote (complete counting), so the levels sum to
  `total_authors`.
- `fit.alpha` and `fit.C` come from a least-squares line through log10(authors) against
  log10(papers), over every level with no tail cutoff. `fit.r_squared` is the R² of that
  line. A few single authors with many papers carry as much weight as the many authors with
  one paper and pull alpha towards 1, so read alpha together with the distribution.
- `fit.goodness_of_fit` is the Kolmogorov-Smirnov test of Pao (1985). It compares the
  observed cumulative share of authors with the Lotka distribution for the fitted alpha.
  That distribution has C = 1 / zeta(alpha) (`expected_single_paper_share`), so the test
  needs alpha > 1. `consistent_with_lotka` is `true` when `D` is below the 0.01-level
  critical value 1.63 / sqrt(N). That formula holds only for more than 35 authors, so
  smaller corpora get `D` without a verdict.
- With fewer than 3 distinct productivity levels, or the same number of authors at every
  level, `fit` is `null` and `reason` says why. Two points always fit a line exactly, so
  an exponent from them would mean nothing.

The methodology export recomputes the fit from the included records and logs the method,
its parameters, the distribution and the result, or the reason no fit was made, under
"AUTHOR PRODUCTIVITY (Lotka's law)". The distribution line is enough to recompute alpha,
C, R² and D from the log alone. The `lotka` block is an additive field, so `schema_version` stays `"1.0"`.

## Methodology export from scripts

`GET /api/projects/{id}/export/methodology` returns the citable PRISMA-aligned text log.
`GET /api/projects/{id}/export/prisma` returns the SVG. Both reflect manual exclusions
made through the toggle / bulk-exclude endpoints, so a fully programmatic workflow can
still produce a journal-quality methodology section.

### Screening decision log

Every exclude, re-include and bulk-exclude appends one row per changed record to an
append-only screening decision log, in the same transaction as the change. A row holds the
UTC time, the endpoint (`toggle` or `bulk_exclude`, with the citation threshold for bulk
exclusions), the record's exclusion state, reason and stage before and after, and an
optional reviewer label. The bundled sample project logs its one seeded exclusion with
source `sample_seed` and no reviewer. BibMedEd has no accounts, so the label is whatever the client
sends in the `X-Reviewer` header. Use ASCII letters, digits, spaces and `. _ @ ' ( ) -`,
start with a letter or digit, and keep it to 64 characters at most. Anything else is
rejected with `422`. Without the header no reviewer is recorded, and none is invented.

```python
c.patch(f"/api/projects/{pid}/publications/{pub_id}/exclude",
        json={"reason": "wrong_population"}, headers={"X-Reviewer": "Reviewer A"})
```

The methodology log has a "Screening decision history" section. It gives the number of
decisions (exclusions, reversals where an excluded record is re-included, and reason or
stage changes), the first and last decision times, exclusion decisions by stage and
reason, every bulk-exclude request, and the reviewer labels seen. Each bulk-exclude request
gets a `run_id` (a UUID) that is stored on every decision row it writes. It also gets a
`bulk_exclude` methodology step with the run id, the threshold and the matched, excluded
and skipped counts. A request that matches nothing therefore still shows up in the export.
These steps cover the whole project. They are listed in this section and are not counted
in the pipeline totals or the PRISMA diagram. The export bundle adds
`<project>-screening-decisions-<date>.csv` with one row per decision, including its
`run_id`. The log starts at Alembic revision `0006_screening_decisions` and is not
backfilled, so the section also counts excluded records that have no logged decision.
Downgrading that revision refuses to drop logged decisions unless
`BIBMEDED_ALLOW_LOSSY_DOWNGRADE=1` is set.

## Screening stages

PRISMA 2020 reports screening in two stages: title/abstract screening of *records* and
full-text assessment of *reports*. Every exclusion carries a `screening_stage`:

| Value | PRISMA 2020 box |
|---|---|
| `title_abstract` | Records excluded (beside "Records screened") |
| `full_text` | Reports excluded, or Reports not retrieved when the reason is `fulltext_unavailable` |

Both exclude endpoints accept an optional `screening_stage`. When it is omitted or `null`:

- reason `fulltext_unavailable` is recorded at `full_text`, because PRISMA 2020 counts a
  report that could not be retrieved under "Reports not retrieved", a full-text box;
- every other reason is recorded at `title_abstract`, so clients written before stages
  existed keep their old meaning.

Sending `fulltext_unavailable` with an explicit `"screening_stage": "title_abstract"` is a
contradiction and returns `422` whenever the request would exclude. The API rejects it rather
than silently changing the stage.

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
`exclusion_reason` and `screening_stage`, whatever the body says (a re-include is never
refused for the contradiction above). A record has one stage,
the stage it was excluded at; to move an exclusion to the other stage, re-include it and
exclude it again. `GET /api/projects/{id}/publications` returns `screening_stage` on every
publication (`null` while it is included). The data exports (CSV, RIS, Web of Science, JSON) contain
only included records, so stages appear in exports through the methodology log and the PRISMA
diagram counts.

The flow diagram counts *reports sought for retrieval* as records screened minus
title/abstract exclusions, and *reports assessed for eligibility* as reports sought minus
reports not retrieved. The methodology log lists both stages with per-reason counts.

Alembic revision `0004_screening_stage` backfills exclusions that existed before stages:
`fulltext_unavailable` exclusions become `full_text` (so they appear under "Reports not
retrieved"), and every other exclusion becomes `title_abstract`. If any excluded record still
has no stage, both exports count it by the same rule (`fulltext_unavailable` under "Reports
not retrieved", anything else at title/abstract) and say how many there are.
Downgrading the revision refuses to run while full-text exclusions exist, because it would
erase their stage. Export the methodology log first, then set
`BIBMEDED_ALLOW_LOSSY_DOWNGRADE=1` to proceed.

These are additive response fields, so `schema_version` stays `"1.0"`.
