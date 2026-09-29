# Self-Hosting Guide

BibMedEd runs as a set of Docker containers. You need **Docker** (with Compose) and **Git**.

**Never used Docker?** Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) for your OS (Mac/Windows/Linux — free for academic and non-commercial use). After installing, open Docker Desktop once so it can start its background service, then proceed with the Quick Start below. The whole BibMedEd stack runs locally inside the containers — no cloud account, no external services. Git can be installed from [git-scm.com](https://git-scm.com/downloads).

**Want to look around before installing anything?** Read the [end-to-end case study](case-study.md) — it walks through a real research question with screenshots and a sample methodology log so you can decide if BibMedEd fits your workflow before committing to the install.

## Quick Start

```bash
git clone https://github.com/ata381/BibMedEd
cd BibMedEd/bibmeded
docker compose up
```

After the containers finish starting (usually 30-60 seconds the first time), open [http://localhost:3000](http://localhost:3000) — that's BibMedEd. The interactive API docs are at [http://localhost:8000/docs](http://localhost:8000/docs).

This starts five services:

| Service | Port | Description |
|---------|------|-------------|
| Frontend | `localhost:3000` | Next.js web interface |
| API | `localhost:8000` | FastAPI backend |
| Worker | — | Celery task processor |
| PostgreSQL | `localhost:5432` | Database |
| Redis | `localhost:6379` | Message broker + cache |

The database schema is created automatically on first startup.

## Security model

!!! warning "BibMedEd has no built-in authentication"
    BibMedEd is designed as a **single-tenant, self-hosted** tool for one research team — there is no login, no user accounts, and no per-project access control anywhere in the API. Every endpoint (list projects, run searches, read or export publications, bulk-exclude records, delete a project) trusts the numeric ID in the URL with no notion of an "owner." That's a reasonable tradeoff for a tool that runs on `localhost` or inside a lab's private network, but it means **anyone who can reach the API has full read/write access to every project** — including via the [one-click "Deploy to Cloud" button](https://github.com/ata381/BibMedEd#deploy-to-cloud), which provisions a publicly reachable `*.onrender.com` URL by default with no credentials required.

    Before exposing BibMedEd to the public internet, do one of the following:

    - **Keep it private (recommended)** — run it on `localhost` or inside a VPN/private network, which is the default `docker compose up` setup. Don't forward ports 3000/8000 to the public internet.
    - **Restrict by IP** — Render's [Inbound IP Rules](https://render.com/docs/inbound-ip-rules) (Scale/Enterprise plans) let you allowlist your lab's IP range for the `bibmeded-api` and `bibmeded-frontend` web services so only your team can reach them.
    - **Put an auth proxy in front** — add HTTP basic auth with a reverse proxy such as [Caddy's `basicauth` directive](https://caddyserver.com/docs/caddyfile/directives/basicauth) or nginx's `auth_basic`, so every request needs a shared password before it reaches BibMedEd.

    Treat an unprotected BibMedEd deployment the same way you'd treat an admin panel with no login screen — because that's exactly what it is.

## Public read-only demo

Setting `BIBMEDED_READ_ONLY=true` turns an instance into a public demo that visitors can explore without installing anything, and that they cannot change.

When the flag is on:

- **Every non-`GET`/`HEAD`/`OPTIONS` request is rejected with `403`** and `{"detail": "...read-only public demo...", "read_only": true}`. This is enforced by a middleware that runs before routing, so it also covers endpoints added in future releases and paths that don't exist. Blocked today: creating, renaming, or deleting projects; creating the sample project; triggering searches; bulk or single exclusion; and running analyses.
- **No outbound API calls can be triggered.** Searches (PubMed, OpenAlex, CrossRef, Semantic Scholar, Lens.org) and iCite enrichment only ever run inside a Celery task dispatched by `POST /search`, which is blocked. A read-only deploy therefore needs **no Redis and no worker**, and `/api/ready` reports `"redis": "skipped"`.
- **Database writes are refused as a second line of defence.** Request-scoped sessions raise on flush, which is returned as `403`. `GET /search/{query_id}` still reports a stale running search as `failed`, but no longer persists that change.
- **The bundled sample project is seeded on startup** (if missing), and all six analyses are precomputed so the dashboard has data even though `POST /analysis/{type}` is blocked. Seeding is idempotent and fails the startup loudly if the database is unreachable.
- **All exports keep working** (CSV, RIS, JSON, PRISMA SVG, methodology log, bundle zip) because they are `GET` downloads.
- `GET /api/config` returns `{"read_only": true}`; the web UI uses it to show a "Read-only demo" banner and hide create/delete/search controls.

Run the demo against its **own database** — never point a read-only instance at a database that holds real projects, since every project in it becomes publicly readable.

!!! warning "Residual risks"
    Read-only mode stops mutation and outbound calls; it does not make a public instance hardened.

    - **Denial of service.** Every read still hits the database, and `/export/bundle` builds a zip in memory. Put a reverse proxy or CDN in front with a per-IP rate limit (for example nginx `limit_req zone=bibmeded burst=20` at around 5 requests/second, or Caddy's `rate_limit`, or Cloudflare rate-limiting rules), plus request-size and timeout limits.
    - **No rate limiting in BibMedEd itself.** The application does not throttle clients; that has to happen at the proxy.
    - **Everything in the database is public.** Only seed demo data.
    - **Interactive API docs remain available** at `/docs`. "Try it out" on a write endpoint just returns `403`, but you can hide the docs at the proxy if you prefer.
    - **Configuration mistakes.** The flag defaults to `false`; if the environment variable is missing or misspelled the instance is fully writable. Check `GET /api/config` after every deploy.

## Configuration

Copy `.env.example` to `.env` to customize:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `BIBMEDED_PUBMED_API_KEY` | *(empty)* | Optional. Register free at [NCBI](https://www.ncbi.nlm.nih.gov/account/) for 10 req/s (default is 3 req/s) |
| `BIBMEDED_LENS_API_KEY` | *(empty)* | Required only for Lens.org searches. Scholarly API bearer token |
| `BIBMEDED_READ_ONLY` | `false` | Public demo mode — see [Public read-only demo](#public-read-only-demo) |
| `POSTGRES_USER` | `bibmeded` | Database username |
| `POSTGRES_PASSWORD` | `bibmeded` | Database password |
| `POSTGRES_DB` | `bibmeded` | Database name |

All defaults work out of the box — no `.env` file is required.

## Stopping

```bash
docker compose down
```

## Resetting the Database

To wipe all data and start fresh:

```bash
docker compose down -v
docker compose up
```

The `-v` flag removes the PostgreSQL data volume.

## Development Setup

For contributors, the `docker-compose.override.yml` file automatically enables:

- Hot-reload on Python file changes
- Source code volume mounts

To disable dev mode (e.g., for local production testing), rename or remove the override file:

```bash
mv docker-compose.override.yml docker-compose.override.yml.bak
docker compose up --build
```

## Health Check

Verify the API is running:

```bash
curl http://localhost:8000/api/health
# {"status": "ok"}
```

## Liveness and readiness probes

For Docker / Kubernetes / Render and any orchestrator that needs a deep healthcheck, BibMedEd exposes two split probes:

- **`GET /api/live`** — liveness. Returns `{"status": "alive"}` with no I/O. Suitable for the docker-compose `healthcheck.test` on the `api` service and the Kubernetes `livenessProbe`. Never fails as long as the process is up.
- **`GET /api/ready`** — readiness. Pings Postgres (`SELECT 1`) and Redis (`PING`). Returns `200 {"status":"ready","checks":{"db":"ok","redis":"ok"}}` when both are reachable, `503 {"status":"not_ready","checks":{...}}` otherwise. Use as the Kubernetes `readinessProbe` or the load balancer healthcheck.

Example docker-compose snippet:

```yaml
services:
  api:
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8000/api/live"]
      interval: 30s
      timeout: 5s
      retries: 3
```

Every API response includes an `X-Request-ID` header (auto-generated unless the client supplies one). When filing a bug, include this id so logs can be correlated end-to-end.
