# Contributing to BibMedEd

Thanks for considering a contribution. BibMedEd is built so that the most useful change you can make — adding a new bibliographic data source — is also the easiest. This guide walks through the three contribution paths in order of impact.

## Three ways to contribute

### 1. Write an adapter (highest leverage)

Every new adapter immediately broadens the literature base every BibMedEd user can analyse. The adapter API is intentionally small: implement `search` and `fetch`, map the source's record format to `RawRecord`, and let the registry auto-discover the class.

- Read the [adapter guide](https://ata381.github.io/BibMedEd/adapters/) for a walkthrough of the `OpenAlexAdapter`.
- Check [`GOOD_FIRST_ISSUES.md`](GOOD_FIRST_ISSUES.md) for vetted source ideas you can claim.
- Open an [adapter request issue](.github/ISSUE_TEMPLATE/adapter_request.yml) to claim a source before you start so we don't duplicate work.

A good adapter PR includes:

- A class in `bibmeded/bibmeded/adapters/<source>.py` subclassing `BaseSourceAdapter`. The registry auto-discovers any `BaseSourceAdapter` subclass dropped here — **you do NOT need to touch `__init__.py` or any registration file**. Drop the module, set `name` / `display_name` / `requires_api_key` on the class, and the `/api/adapters` route + the frontend source picker pick it up at the next request.
- A fixture-based test under `bibmeded/tests/test_adapters_<source>.py` that exercises `search` and `fetch` against captured JSON / XML payloads — no live API calls in CI.
- A one-line mention in `README.md`'s feature list, plus source-specific credentials, caveats, or setup notes in `docs/adapters.md`. The guide is manually maintained, so update it when a new adapter ships.

**Load-bearing invariants — easy to miss, hard to debug:**
- Lowercase DOIs at the adapter boundary (`doi.lower()`). The cross-source dedup keys on DOI string equality and will silently miss duplicates across sources if cases differ.
- Pass `mesh_terms=[]` explicitly when your source doesn't provide MeSH (every non-PubMed adapter does this). The `RawRecord` dataclass default would also work, but explicit empties signal intent and make the gap visible in code review.
- See `bibmeded/bibmeded/adapters/base.py` — the `RawRecord` docstring spells out every invariant in one place.

### 2. Report a bug or request a feature

Use the [issue templates](.github/ISSUE_TEMPLATE/). Bugs need a reproduction; feature requests need a problem statement (what research workflow is currently painful).

### 3. Improve docs and examples

`docs/` is rendered with MkDocs Material and deployed automatically on merge to `master`. Walkthroughs of real bibliometric studies you have run with BibMedEd are especially welcome — they double as marketing and tutorials.

## New-contributor checklist

1. Pick an open item from [`GOOD_FIRST_ISSUES.md`](GOOD_FIRST_ISSUES.md), or propose one with an issue template.
2. Comment on the existing issue before starting so two contributors do not duplicate work.
3. Fork the repository, branch from `master`, and run the focused tests while you work.
4. Open a PR with `Closes #N`, fixture-based tests, and any user-facing documentation the change needs.

Questions and early design ideas are welcome in [GitHub Discussions](https://github.com/ata381/BibMedEd/discussions). Maintainers aim to acknowledge contribution questions and claims within three working days; if a thread is quiet for a week, one friendly ping is welcome.

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

### Keeping the e2e mocks in sync with the API

The Playwright suite runs against hand-written mocks in `bibmeded/frontend/e2e/mock-api.ts`. Two checks keep them honest:

- `bibmeded/tests/test_api_shapes_contract.py` seeds the sample project, calls every analysis endpoint and compares the response shapes (keys and value types) with `bibmeded/frontend/e2e/fixtures/api-shapes.json`. It fails when the fixture is stale.
- `bibmeded/frontend/e2e/api-contract.spec.ts` fails when a mocked analysis response is missing a field, has an extra one, or uses the wrong type, and names the field.

If you change an analysis response on purpose, refresh the fixture and then fix the mocks:

```bash
cd bibmeded
UPDATE_API_SHAPES=1 pytest tests/test_api_shapes_contract.py   # rewrites api-shapes.json
cd frontend
PLAYWRIGHT_SKIP_WEBSERVER=1 npx playwright test api-contract   # lists every drifted mock field
```

Commit the refreshed `api-shapes.json` together with the backend change. The sample data cannot show every shape, so the pytest file declares two kinds of gap. `KNOWN_NULLABLE` lists fields the code can return as `null`, typed even when the sample only produces `null`. `KNOWN_ITEMS` gives the element shape for lists the sample leaves empty. The test fails, naming the path, if a new gap appears undeclared.

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

## AI-assisted contributions

AI coding tools are welcome here. The bar is the same as for any PR:

- You must understand, and be able to explain, every line you submit.
- Run the tests (`pytest -q`) and check the behaviour yourself; do not rely on the tool's claim that it works.
- Disclose substantial AI assistance in the PR description (which tool, and roughly what it produced).
- Low-effort generated PRs (unreviewed output, untested changes, boilerplate that ignores the adapter contract) will be closed.

## Code of Conduct

Participation in this project is governed by the [Contributor Covenant](CODE_OF_CONDUCT.md).

## Security

Do **not** open public issues for security problems. See [SECURITY.md](SECURITY.md) for private disclosure.

## License

By contributing you agree that your contributions are licensed under the project [MIT License](LICENSE).
