# Contributing to BibMedEd

Thanks for considering a contribution. BibMedEd is built so that the most useful change you can make — adding a new bibliographic data source — is also the easiest. This guide walks through the three contribution paths in order of impact.

## Three ways to contribute

### 1. Write an adapter (highest leverage)

Every new adapter immediately broadens the literature base every BibMedEd user can analyse. The adapter API is intentionally small: implement `search` and `fetch`, map the source's record format to `RawRecord`, register the class, done.

- Read the [adapter guide](https://ata381.github.io/BibMedEd/adapters/) for a walkthrough of the `OpenAlexAdapter`.
- Check [`GOOD_FIRST_ISSUES.md`](GOOD_FIRST_ISSUES.md) for vetted source ideas you can claim.
- Open an [adapter request issue](.github/ISSUE_TEMPLATE/adapter_request.yml) to claim a source before you start so we don't duplicate work.

A good adapter PR includes:
- A class in `bibmeded/app/adapters/<source>.py` subclassing `BaseSourceAdapter`.
- Registration in `bibmeded/app/adapters/__init__.py`.
- A fixture-based test under `bibmeded/tests/test_adapters_<source>.py` that exercises `search` and `fetch` against captured JSON / XML payloads — no live API calls in CI.
- A note in `docs/adapters.md` and a one-line mention in `README.md`'s feature list.

### 2. Report a bug or request a feature

Use the [issue templates](.github/ISSUE_TEMPLATE/). Bugs need a reproduction; feature requests need a problem statement (what research workflow is currently painful).

### 3. Improve docs and examples

`docs/` is rendered with MkDocs Material and deployed automatically on merge to `master`. Walkthroughs of real bibliometric studies you have run with BibMedEd are especially welcome — they double as marketing and tutorials.

## Local development

```bash
git clone https://github.com/ata381/BibMedEd
cd BibMedEd/bibmeded

# Backend — Python 3.12+
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q

# Full stack
docker compose up
```

Tests use in-memory SQLite and require no external services. The full Docker stack provisions Postgres, Redis, the FastAPI API, a Celery worker, and the Next.js frontend.

## Code style

- Python: ruff-compatible, type hints on public functions, `async` everywhere in the request path.
- TypeScript / React: the frontend uses Next.js 16 App Router; co-locate components with their route.
- Keep commits scoped. Conventional-commit-style prefixes (`feat:`, `fix:`, `docs:`, `chore:`, `perf:`, `sec:`) are encouraged — recent history shows the pattern.

## Pull request flow

1. Fork and create a branch off `master`.
2. Make focused commits; rebase rather than merge `master` into your branch.
3. `pytest -q` must pass; CI will re-run it on Python 3.12 and 3.13.
4. Fill in the [PR template](.github/PULL_REQUEST_TEMPLATE.md). Link the issue you're closing.
5. A maintainer will review. Most adapter PRs are reviewed within a week.

## Code of Conduct

Participation in this project is governed by the [Contributor Covenant](CODE_OF_CONDUCT.md).

## Security

Do **not** open public issues for security problems. See [SECURITY.md](SECURITY.md) for private disclosure.

## License

By contributing you agree that your contributions are licensed under the project [MIT License](LICENSE).
