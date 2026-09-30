---
name: new-adapter
description: Recipe for adding a BibMedEd data-source adapter (Europe PMC, arXiv, DOAJ, CORE, BASE, Dimensions, …) end to end, matching the existing adapters exactly.
---

# New adapter

Reference: `bibmeded/bibmeded/adapters/base.py` (contract), `openalex.py` (keyless, cursor pagination), `lens.py` (API key, offset pagination, config error), docs at `docs/adapters.md`.

1. Read the source's API docs; record base URL, auth, rate limit, page size, max offset, and which IDs it exposes (DOI, PMID, PMCID, native ID).
2. Capture 2–3 real responses by hand (search page, last page/empty, a record with missing fields) and save them as fixtures under `bibmeded/tests/fixtures/<source>/`. Strip any keys/emails. Tests must only use fixtures.
3. Write `tests/test_adapters_<source>.py` first: search count, pagination stops at total and at the result cap, `fetch` maps to `RawRecord`, DOI normalisation (lower-case, no `https://doi.org/` / `doi:` prefix), missing-ID records handled, malformed response raises a clear error, key-missing error if keyed.
4. Implement `bibmeded/adapters/<source>.py` subclassing `BaseSourceAdapter`. Put every available identifier in `external_ids` — cross-source dedup depends on it. Only call the documented host (SSRF: never build hosts from response data).
5. Register it: `bibmeded/adapters/registry.py`, settings in `bibmeded/adapters/settings.py` (`adapter_kwargs`, `adapter_configuration_error` if keyed), `bibmeded/config.py` for `BIBMEDED_<SOURCE>_*`, the search API source schema, compose env passthrough if keyed.
6. Mirror the registry/router/worker/CLI wiring tests that exist for `lens` (`grep -rn lens bibmeded/tests`).
7. Docs: source row in `docs/adapters.md` / built-in sources list, README feature list, status link in `GOOD_FIRST_ISSUES.md`.
8. Verify with `.claude/harness/verify.md` (backend + docs rows).
