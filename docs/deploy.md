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

## Configuration

Copy `.env.example` to `.env` to customize:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `BIBMEDED_PUBMED_API_KEY` | *(empty)* | Optional. Register free at [NCBI](https://www.ncbi.nlm.nih.gov/account/) for 10 req/s (default is 3 req/s) |
| `BIBMEDED_LENS_API_KEY` | *(empty)* | Required only for Lens.org searches. Scholarly API bearer token |
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
