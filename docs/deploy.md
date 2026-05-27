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

## Configuration

Copy `.env.example` to `.env` to customize:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `BIBMEDED_PUBMED_API_KEY` | *(empty)* | Optional. Register free at [NCBI](https://www.ncbi.nlm.nih.gov/account/) for 10 req/s (default is 3 req/s) |
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
