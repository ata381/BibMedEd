# BibMedEd — Project Conventions for Claude

This file orients automated reviewers and `@claude` runs to the conventions used in this repo. Humans should also read [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Repo layout

```
bibmeded/
  app/                # FastAPI backend
    adapters/         # Data-source adapters (base.py defines RawRecord + BaseSourceAdapter)
    analysis/         # Bibliometric modules (publications, authors, countries, ...)
    routers/          # HTTP routes
    services/         # Pipeline orchestration
    workers/          # Celery tasks
    models/           # SQLAlchemy 2.0 ORM
  frontend/           # Next.js 16 + React 19 + D3.js
  tests/              # pytest, SQLite in-memory
  alembic/            # DB migrations (Postgres in prod, create_all in dev/CI)
docs/                 # MkDocs Material site, deployed on push to master
```

## Code conventions

- **Python 3.12+**, type hints on public functions, `async` everywhere in the request/worker path.
- **SQLAlchemy 2.0** style (`Mapped[...]`, `mapped_column`).
- **Adapters** must subclass `BaseSourceAdapter` and return `RawRecord` objects. Cross-source deduplication relies on `external_ids` (DOI, PMID, OpenAlex ID, etc.).
- **Tests** use fixture-based JSON / XML payloads — never hit live APIs in CI.
- **Frontend**: Next.js App Router, Tailwind CSS, D3.js for network graphs. Co-locate components with their route.
- **No comments explaining what code does** — naming should suffice. Reserve comments for non-obvious why.

## Commit and PR style

- Conventional-commit prefixes: `feat`, `fix`, `docs`, `chore`, `perf`, `sec`, `refactor`.
- Keep commits scoped. Rebase rather than merge `master` into feature branches.
- PRs use the template in `.github/PULL_REQUEST_TEMPLATE.md`.

## Running things

```bash
# Backend tests (fast, no services needed)
cd bibmeded && pip install -e ".[dev]" && pytest -q

# Full stack
cd bibmeded && docker compose up
# Frontend → http://localhost:3000, API → http://localhost:8000/docs
```

## Review priorities

When reviewing a PR, weight findings in this order:

1. **Correctness** — incorrect dedup keys, lost records in pagination, off-by-one in batch sizing, wrong DB cascade behaviour.
2. **Security** — input validation on adapter responses, SQL injection in raw queries, secret leakage in logs, SSRF in adapter HTTP clients.
3. **Reproducibility** — every pipeline step must be loggable in the methodology export. Don't silently coerce or drop fields.
4. **Performance** — N+1 queries, unbounded result sets, memory blow-up in large fetches (use streaming generators).
5. **API stability** — public `RawRecord` / adapter contract changes are breaking and need a migration note.

Style nits below the bar of correctness should be grouped or skipped.

## What `@claude` should and should not do

- ✅ Open PRs that add new adapters, fix bugs, improve docs, add tests.
- ✅ Respond to review comments by pushing fixes to the existing PR branch.
- ✅ Triage stale issues with a one-paragraph status note.
- ❌ Modify `LICENSE`, `CITATION.cff` authorship, or `render.yaml` service plans without explicit human approval.
- ❌ Add dependencies that aren't trivially replaceable (heavyweight ML stacks, paid SaaS SDKs) without flagging in the PR.
- ❌ Auto-merge — leave merge to a human maintainer.
