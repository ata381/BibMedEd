# Self-Hosting Guide

BibMedEd runs as a set of Docker containers. You need **Docker** (with Compose) and **Git**.

## Quick Start

```bash
git clone https://github.com/ata381/bibmeded
cd bibmeded/bibmeded
docker compose up
```

This starts five services:

| Service | Port | Description |
|---------|------|-------------|
| Frontend | `localhost:3000` | Next.js web interface |
| API | `localhost:8000` | FastAPI backend |
| Worker | — | Celery task processor |
| PostgreSQL | `localhost:5432` | Database |
| Redis | `localhost:6379` | Message broker + cache |

The database schema is created automatically via Alembic migrations on first startup.

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
