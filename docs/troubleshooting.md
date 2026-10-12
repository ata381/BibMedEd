# Troubleshooting and FAQ

This page collects the problems people run into most often, with the message you will see and what to do about it. It is written for researchers, not developers. You do not need to read any code.

Most fixes need a terminal open in the `bibmeded/` folder of your BibMedEd download, the folder that holds `docker-compose.yml`. Every `docker compose` command below is run from there.

If your problem is not here, see [Where do I report a bug?](#where-do-i-report-a-bug) at the end.

## Install and start

### `docker compose up` says it cannot connect to Docker

```text
Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?
```

On Windows the same problem usually mentions `dockerDesktopLinuxEngine` and ends with `The system cannot find the file specified.`

Docker is installed but its background service is not running. Open **Docker Desktop**, wait until it reports that the engine is running, then run `docker compose up` again. Docker Desktop has to be open whenever you use BibMedEd. See the [Self-Hosting Guide](deploy.md) if you have not installed Docker yet.

### A port is already in use (3000, 8000, 5432 or 6379)

Docker's wording varies by system, but it names the port, for example:

```text
Bind for 0.0.0.0:5432 failed: port is already allocated
```

BibMedEd publishes four ports on your computer: `3000` (web app), `8000` (API), `5432` (PostgreSQL) and `6379` (Redis). Another program, or a second copy of BibMedEd, is already using one of them.

1. Find the program using the port. On Windows: `netstat -ano | findstr :5432`. On macOS or Linux: `lsof -i :5432`.
2. If it is an old BibMedEd stack, stop it with `docker compose down`.
3. If it is another program, such as a PostgreSQL you installed yourself, stop that program while you use BibMedEd.

If you cannot stop a local PostgreSQL or Redis, you can move BibMedEd's copy instead. In `docker-compose.yml`, change only the number on the left of the colon, for example `"5432:5432"` to `"5433:5432"`. The BibMedEd containers talk to the database and Redis inside Docker, so nothing else needs to change.

Ports `3000` and `8000` are harder to move: the web app has the API address (`NEXT_PUBLIC_API_URL`) built in, and the API only accepts requests from the web app's address (`BIBMEDED_CORS_ORIGINS`). Free those two ports rather than changing them.

### The `api` or `worker` container exits with "no such file or directory" (Windows)

```text
no such file or directory
```

If this mentions `scripts/entrypoint.sh`, the start-up script was checked out with Windows line endings. Linux containers cannot run it that way. The repository now forces Unix line endings for shell scripts, but a copy cloned before that fix keeps the old file.

Clone the repository again into a new folder, then rebuild:

```bash
git clone https://github.com/ata381/BibMedEd
cd BibMedEd/bibmeded
docker compose up --build
```

`--build` matters: without it Docker reuses the image that contains the broken file.

### Does it run on an Apple Silicon Mac (M1 and later)?

Nothing in BibMedEd is specific to Intel or ARM. The compose files do not pin a CPU platform, and every image is built from an official base image (`postgres:16-alpine`, `redis:7-alpine`, `python:3.12-slim`, `node:20-alpine`) that is published for both. Plain `docker compose up` is all you need, with no extra flags.

BibMedEd's automated tests do not run on ARM. If a build fails on a Mac, please [report it](#where-do-i-report-a-bug) with the full output.

### I started the demo and it is on port 3100, not 3000

That is intended. The read-only demo (`docker compose -f docker-compose.demo.yml up --build`) uses <http://localhost:3100> for the web app and <http://localhost:8100/docs> for the API, so it can run next to your normal BibMedEd on 3000 and 8000. It has no database server, no Redis and no worker. It shows only the bundled synthetic sample and does not let you create projects or run searches. See [Run the demo locally](deploy.md#run-the-demo-locally).

Stop it and discard its data with:

```bash
docker compose -f docker-compose.demo.yml down -v
```

### How do I start over with an empty database?

This deletes every project:

```bash
docker compose down -v
docker compose up
```

`-v` removes the PostgreSQL data volume. See [Resetting the Database](deploy.md#resetting-the-database). Contributors can also run `docker compose exec api python scripts/reset_db.py`, which drops and recreates every table. That script is meant for development only.

## Searches

### PubMed searches fail with "429 Too Many Requests"

In the web app the search stops and you see:

```text
Search failed. Please try again.
```

The worker log (`docker compose logs worker`) shows the reason:

```text
run_search failed query_id=12
...
httpx.HTTPStatusError: Client error '429 Too Many Requests' for url 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?...'
```

NCBI limits how many requests one computer may send to PubMed: 3 per second without an API key and 10 per second with one. BibMedEd paces each search at 3 requests per second. The worker runs up to two searches at the same time, so two PubMed searches together, or other PubMed tools on the same network, can go over the keyless limit.

Fix:

1. Create a free API key in your [NCBI account settings](https://www.ncbi.nlm.nih.gov/account/).
2. Copy `.env.example` to `.env` in the `bibmeded/` folder if you have not already, and set `BIBMEDED_PUBMED_API_KEY=your_key`.
3. Restart so the containers pick it up: `docker compose down`, then `docker compose up`.
4. Run the search again.

The key raises NCBI's limit for you. BibMedEd still sends at most 3 requests per second per search, so it does not search faster. It does stop two searches at once from going over the limit. Without a key, run one PubMed search at a time.

### Lens.org searches fail: "Lens searches require BIBMEDED_LENS_API_KEY"

Lens.org is the only built-in source that needs a key. Without one, BibMedEd refuses the search before contacting Lens. The API answers with status `503`:

```json
{"detail": "Lens searches require BIBMEDED_LENS_API_KEY"}
```

The web app only shows a general message:

```text
Could not start search. Is the backend running?
```

The command line prints `Lens searches require BIBMEDED_LENS_API_KEY`, and `bibmeded sources` lists Lens as `missing BIBMEDED_LENS_API_KEY`.

Fix: get a Scholarly API token from Lens.org, add `BIBMEDED_LENS_API_KEY=your_token` to `bibmeded/.env`, then run `docker compose down` and `docker compose up`. The Lens chip on the search page is marked "(API key)" as a reminder.

### My search finished with 0 results, but the query is correct

The search page shows `0 publications ready.` and the results page says "No publications found". Check these in order:

1. **Publication years.** The Query Builder starts at 2022 to 2025. Widen the range if your topic is older.
2. **PubMed syntax sent to another database.** Field tags such as `[Mesh]`, `[tiab]` and `[PDAT]` only work in PubMed. OpenAlex, CrossRef, Semantic Scholar and Lens.org take plain keywords with `AND`, `OR` and `NOT`. Remove the tags, or switch the source to PubMed.
3. **Advanced Query (Raw) mode.** For PubMed, the year range is part of the query text: it is the `[PDAT]` clause the Query Builder adds. In raw mode, type it yourself. For the other sources, the year fields are hidden in raw mode, but the years you last set in the Query Builder are still applied. Switch back to the Query Builder to check them.
4. **Test the count without fetching anything.** From the command line, `bibmeded search "your query" --source openalex --dry-run` prints `Estimated results: N`. The dry run ignores year limits, so a large number here and 0 in the app points to the years.

### The results page says "only the first 2,000 were fetched"

```text
Search returned 5,400 records — only the first 2,000 were fetched.
```

Each search fetches at most 2,000 records by default, so one broad query cannot run for hours. When the database had more, BibMedEd says so instead of truncating silently. The methodology log records the same thing:

```text
    Results: 5400 records (capped at max_results=2000; full set not retrieved)
```

For a systematic review you need the full set. Either:

- **Narrow the query** (fewer years, more specific terms) until it returns fewer than 2,000 records, or run it in parts, for example one search per range of years. Searches in the same project are deduplicated against each other.
- **Raise the cap, up to 10,000.** The web app always asks for 2,000. Use the API page at <http://localhost:8000/docs>: open `POST /api/projects/{project_id}/search`, choose **Try it out**, and send `"max_results": 10000` with your query. See [Scripting](scripting.md) for a script that does the same. The API rejects values above 10,000. A search has 10 minutes to finish (the worker's time limit), so very large searches can also fail. Splitting by year avoids both limits.

The "Records identified" number can be lower than the database's full total for very large searches, because BibMedEd stops collecting IDs once it has enough. `--dry-run` gives the full count.

### My search stays on "Search dispatched..." and never progresses

Searches run in the separate **worker** container. If the worker is not running, the search waits in the queue with status `pending` and nothing moves. The command line shows the same thing:

```text
Status: pending
Status: pending
...
Search timed out. Check worker logs
```

Check the containers:

```bash
docker compose ps
docker compose logs worker
```

If `worker` is missing or has exited, start it with `docker compose up -d worker`. Searches waiting in the Redis queue are picked up when the worker starts. If a search is still `pending` after that, for example because Redis was restarted in the meantime, run it again. If the worker log shows an error, include it in a bug report.

A search that has been `running` for more than 15 minutes is reported as `failed`, so it does not appear stuck forever. Run it again once the worker is healthy.

## Deduplication

### Why are two records with the same title both kept?

BibMedEd only treats two records as duplicates when they share the same **DOI** or the same **PMID**, exactly. It never compares titles. Titles are not unique: corrections, conference abstracts and preprints often repeat a title word for word, and merging those automatically would hide real records from your PRISMA counts. DOIs are compared without letter case and without a leading `https://doi.org/`, `http://doi.org/` or `doi:`.

So two records with the same title are both kept when:

- one has a DOI and the other does not, or they have different DOIs, and
- they do not share a PMID.

Records with neither a DOI nor a PMID can never be matched. If you find a duplicate yourself, exclude one copy on the results page with the reason **Duplicate not caught by automated dedup**. The methodology log counts it under that reason.

### Which wins, DOI or PMID?

Either one is enough. A record is a duplicate if its DOI or its PMID matches a record already seen, and the first copy is kept. When both match, the methodology log counts the removal under `doi`, otherwise under `pmid`.

Within one project, BibMedEd also checks every new record against the records already saved, by PMID (or the source's own ID) and DOI. A paper that an earlier search already found is not saved twice, and the copy saved first is kept.

### Where do I find how many duplicates were removed?

There are two places:

- **The results page**: the "Duplicates removed" box in the PRISMA flow, for the latest search.
- **The methodology log** (Export page, Methodology & PRISMA), in the DEDUPLICATION section of each search:

```text
DEDUPLICATION
  Step 3: Cross-source deduplication on DOI and PMID
    Method: exact-match on doi,pmid
    Removed by field: doi=4, pmid=1
    Removed: 5 duplicates (412 → 407)
```

This section only appears when a search removed at least one duplicate. Records skipped because an earlier search in the same project already had them are not listed here. They count as unavailable in that search's DATA COLLECTION step:

```text
    Retrieved: 380 of 400 (20 unavailable)
```

The "unavailable" count also includes records the database listed but did not return, and records that failed to save. Failed records are listed one by one under `Failed to persist`.

## Screening and PRISMA

### Which screening stage does an exclusion get?

PRISMA 2020 separates title/abstract screening of records from full-text assessment of reports. Each exclusion records one of the two:

- In the web app, the exclusion menu has a **PRISMA screening stage** choice, Title / abstract or Full text. It starts at Title / abstract on each visit and stays on your last choice while you work. **Full-text not retrievable** is always recorded at the full-text stage, because PRISMA reports it as "Reports not retrieved".
- **Exclude 0-citation papers** records its exclusions at title/abstract with the reason "Other / unspecified".
- Through the API, the stage is optional. When you leave it out, `fulltext_unavailable` goes to `full_text` and every other reason goes to `title_abstract`. Details are in [Screening stages](scripting.md#screening-stages).

### "Exclude 0-citation papers" wants to exclude almost everything

Citation counts come from NIH iCite, and BibMedEd only fetches them for **PubMed** searches. Records from OpenAlex, CrossRef, Semantic Scholar and Lens.org have no citation count. The bulk exclusion counts "no citation count" as 0, so it would remove every one of them. The confirmation dialog shows how many publications will be excluded. Read that number before confirming.

If a PubMed search's records all show 0 citations, check the methodology log for `iCite citation count enrichment (failed)`. iCite was unreachable during that search. The search itself still succeeded.

The methodology log records how many records were excluded and why, not the threshold you used. State the threshold in your Methods section.

### The API returns 422 when I exclude with `fulltext_unavailable`

```text
Value error, reason 'fulltext_unavailable' records a report that could not be retrieved, which PRISMA 2020 counts at the full-text stage; use screening_stage 'full_text' or omit it
```

You asked for reason `fulltext_unavailable` at stage `title_abstract`. Those two contradict each other, and BibMedEd refuses rather than quietly changing the stage. Send `"screening_stage": "full_text"`, or leave the stage out. The web app never sends this combination, so you only see this from scripts.

### How do I re-include a record, or move it to the other stage?

On the results page, click **Excluded** on the record. It goes back to included and its reason and stage are cleared. Through the API, calling the exclude endpoint again on an excluded record does the same. A record has only one stage. To move an exclusion to the other stage, re-include it, then exclude it again at the stage you want.

## Analysis

### The dashboard says "No publications to analyze"

The dashboard counts included records that have a publication year. This message means there are none. Either no search has finished, every record is excluded, or no record has a year. Go back to the results page and check the included count.

### The growth summary shows "—" instead of CAGR or doubling time

The publication trends figure shows compound annual growth (CAGR) and doubling time, measured over full calendar years only. When one cannot be calculated, the card says why:

| Message | Meaning |
|---|---|
| `At least two full calendar years of data are required to compute CAGR.` | The included records span fewer than two complete years. |
| `CAGR is undefined because the first full calendar year has zero publications.` | Growth from zero cannot be expressed as a rate. Start the search at a later year. |
| `Doubling time is not defined for non-positive growth (CAGR <= 0).` | Output is flat or shrinking, so it never doubles. CAGR is still shown. |
| `Current incomplete year excluded from growth calculations.` | Not an error. The current year is still in progress, so it is left out. |

### Field maturity is `null` or `"undetermined"`

The field maturity classification is not shown on the dashboard. It is in the publications analysis returned by the API (`field_maturity` in `GET /api/projects/{id}/analysis/publications`). It fits a logistic growth curve to cumulative publication counts:

- **`null`**: fewer than four years between the first and last publication year, or the curve could not be fitted.
- **`"phase": "undetermined"`**: a curve was fitted but explains the data poorly (fit quality below 0.85). BibMedEd does not guess a phase label in that case. Plateau-then-surge fields often end up here.

### The network says "No network data available", or a table is empty

The dashboard network is the co-authorship network. It is empty when no included record lists its authors. Large networks (more than 200 authors) start by showing only about the 100 most productive authors. Lower the **Min. publications** slider to see more.

Other analyses depend on what each source provides:

- **Countries** are read from the end of author affiliation text and match a fixed list of about 50 countries. Semantic Scholar gives no affiliations, so a Semantic Scholar-only project has no country or institution data.
- **Citation counts** are only filled for PubMed searches (see [above](#exclude-0-citation-papers-wants-to-exclude-almost-everything)). Other sources show 0 citations, and author h-indices will be 0.
- **MeSH terms** come from PubMed and Lens.org. For the other sources, keyword analyses use only the keywords that source supplies.

## Exports

### Which file do I open in which program?

| Export | Opens in | Notes |
|---|---|---|
| **RIS** (`.ris`) | Zotero, EndNote, Mendeley | Title, authors, journal, year, DOI, abstract and keywords. |
| **CSV** (`.csv`) | Excel, Google Sheets, R, pandas | One row per record: PMID, DOI, title, authors, journal, year, citations, keywords and abstract. Cells that start with `=`, `+`, `-` or `@` get a leading `'` so the spreadsheet does not treat them as formulas. |
| **JSON** (`.json`) | Scripts and notebooks | A `schema_version` field (currently `"1.0"`), the project name, the date, a `count` and the `publications`. Check `schema_version` before relying on field names. See [Scripting](scripting.md#versioning-contract). |
| **Methodology log** (`.txt`) | Any text editor | The record of every pipeline step. See below. |
| **PRISMA diagram** (`.svg`) | Web browser, Word, PowerPoint, Inkscape | The PRISMA 2020 flow diagram with your counts. |
| **Bundle** (`.zip`) | Your file manager | All five files above plus a manifest. |

CSV, RIS and JSON contain **included records only**. Excluded records and their reasons appear in the methodology log and the PRISMA diagram.

### Where does the methodology log go in my paper?

The log is a plain-text record of what BibMedEd did. It lists, for each search, the exact query, the database, the date and time it ran, how many records were found and retrieved, any cap that was hit, duplicates removed by field, and citation enrichment. After the searches it lists screening decisions by PRISMA stage and reason, then the final number of included studies.

A common pattern:

- In **Methods**, report the databases, the exact queries and search dates, and the deduplication rule (exact match on DOI and PMID). Copy these from the log rather than retyping them.
- Attach the **full log as a supplementary file** and refer to it from Methods.
- Use the **PRISMA SVG** as your flow diagram figure.
- Cite BibMedEd itself. The [case study](case-study.md#7-write-up) has an example sentence, and the citation is on the [home page](index.md#cite).

## Read-only mode

### Every change fails with 403 "read-only public demo"

```json
{"detail": "This BibMedEd instance is a read-only public demo. Install BibMedEd locally to create projects and run your own searches.", "read_only": true}
```

The instance runs with `BIBMEDED_READ_ONLY=true`. That setting blocks every request that would change something: creating or deleting projects, searching, excluding and running analyses. Exports still work. This is deliberate for public demos. See [Public read-only demo](deploy.md#public-read-only-demo).

On your own install, check `bibmeded/.env` and your environment for `BIBMEDED_READ_ONLY=true`. Set it to `false`, then run `docker compose down` and `docker compose up`. The API log prints `BibMedEd mode: read_only=False` at start-up when writes are allowed.

### My own install shows the "Read-only demo" banner

```text
Read-only demo — install locally to run your own searches.
```

If `BIBMEDED_READ_ONLY` is not set to `true`, the web app could not reach the API to ask, and it stays read-only to be safe. The search button then does nothing. Usually the API is still starting or has stopped. Check with:

```bash
docker compose ps
curl http://localhost:8000/api/config
```

When the API answers `{"read_only":false}`, reload the page.

### A misspelled setting is being ignored

At start-up the API log warns about any `BIBMEDED_` variable it does not recognise:

```text
ignoring unrecognised environment variable BIBMEDED_READONLY (typo of a BIBMEDED_* setting?)
```

Fix the spelling and restart. Valid names are listed in `bibmeded/.env.example` and the [configuration table](deploy.md#configuration).

### Can I put my BibMedEd on the internet?

Not as it is. BibMedEd has no login: anyone who can reach it can read, change or delete every project. Keep it on your own computer or a private network, or put an IP allowlist or a password-protecting proxy in front. Read the [Security model](deploy.md#security-model) first.

## Upgrading

### How do I upgrade to a new version?

```bash
git pull
docker compose up --build
```

When the containers start, they update the database structure automatically with `alembic upgrade head`. The log shows `Running Alembic migrations...` before the API starts. Your projects are kept. Let running searches finish before you upgrade.

If you run BibMedEd without Docker, run `alembic upgrade head` from the `bibmeded/` folder after updating.

### A downgrade refuses to run because of full-text exclusions

Going back to a version from before screening stages existed would delete the stage of every full-text exclusion. Those exclusions would then read as title/abstract exclusions. The downgrade stops with:

```text
0004_screening_stage downgrade: 3 publication(s) were excluded at the full-text stage, and dropping publications.screening_stage would erase that stage (they would read as title/abstract exclusions after re-upgrading). Export the methodology log and PRISMA diagram for every affected project first, then re-run with BIBMEDED_ALLOW_LOSSY_DOWNGRADE=1 to accept the loss. Refusing to silently drop reproducibility-critical screening data.
```

First export the methodology log and PRISMA diagram for every affected project. Then set `BIBMEDED_ALLOW_LOSSY_DOWNGRADE=1` for the downgrade command only, to accept the loss.

## Where do I report a bug?

Open an issue on GitHub with the [bug report template](https://github.com/ata381/BibMedEd/issues/new?template=bug_report.yml). It asks for:

- what happened, how to reproduce it, and what you expected;
- your version (`bibmeded --version`, plus `git rev-parse --short HEAD` if you run from a clone);
- how you run BibMedEd (local Docker Compose, Render, or other);
- the output of `docker compose logs api worker` around the failure.

Every API response carries an `X-Request-ID` header. If you have it, include it so the matching log lines can be found.

Other routes:

- **Questions and ideas:** [GitHub Discussions](https://github.com/ata381/BibMedEd/discussions).
- **A new data source:** the [adapter request template](https://github.com/ata381/BibMedEd/issues/new?template=adapter_request.yml).
- **A feature request:** the [feature request template](https://github.com/ata381/BibMedEd/issues/new?template=feature_request.yml).
- **Security problems:** do not open a public issue. Follow [SECURITY.md](https://github.com/ata381/BibMedEd/blob/master/SECURITY.md) to report privately.
