# BibMedEd — Project Conventions for AI Coding Agents

Orients agents (Claude Code, Codex, Cursor, etc.) to the conventions used in this repo. Humans should read [`CONTRIBUTING.md`](CONTRIBUTING.md). An [`AGENTS.md`](AGENTS.md) symlink-equivalent points other agent toolchains here.

## Repo layout

```
bibmeded/
  bibmeded/           # FastAPI backend (Python import package)
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

## Scope guidance for agents

- ✅ Open PRs that add new adapters, fix bugs, improve docs, add tests.
- ✅ Respond to review comments by pushing fixes to the existing PR branch.
- ✅ Triage stale issues with a one-paragraph status note.
- ❌ Modify `LICENSE`, `CITATION.cff` authorship, or `render.yaml` service plans without explicit human approval.
- ❌ Add dependencies that aren't trivially replaceable (heavyweight ML stacks, paid SaaS SDKs) without flagging in the PR.
- ❌ Merge your own PRs if you are a contributor's agent — merging is the maintainer's call.
- ✅ The maintainer's own agents may merge (including `gh pr merge --auto`) once a PR has passed review, the external-PR security screen where applicable, and all required CI checks.

## Contribution merge policy

Well-done contributions are merged, not rewritten. If a PR needs changes of roughly 20+ lines or a design-level rework, ask the contributor in a review. Smaller non-blocking fixes are merged as-is and followed up by the maintainers in a separate PR that credits the contributor.

## Reviewer setup

Codex Cloud handles automatic PR reviews on this repo (see e.g. PR #4). Do not duplicate that loop with a second AI reviewer workflow.

## Maintainer agent harness

`.claude/agents/`, `.claude/skills/` and `.claude/harness/` hold the maintainer's agent roles, workflows, verification matrix and report contract. They are shared by local Claude Code sessions and by the scheduled cloud maintainer agent, whose prompt is in `.claude/harness/cloud-manager-prompt.md`. `.claude/state/`, `settings.json` and hooks stay local and gitignored. Changes to these files, to this file or to `AGENTS.md` change what the maintainer's agents do. They need the maintainer's review and are never auto-merged.

## Security review before pulling external PRs

For PRs from outside contributors (not `ata381`), do the security pass **from afar first** — read the diff via `gh pr diff <n>` / `gh pr view <n>` / `gh api` without checking out the branch. Fetching refs (`git fetch origin pull/<n>/head`) and reading blobs (`git show <ref>:<path>`) is fine since neither executes anything. Do not run `pytest`, install deps, `docker compose up`, pre-commit hooks, or anything else that executes the contributor's code (including their CI-invoked scripts) until the diff has been read and cleared. Flag anything that would run on checkout/build (setup.py/postinstall hooks, entrypoint scripts, CI workflow changes) as CRITICAL regardless of what else the PR does.
