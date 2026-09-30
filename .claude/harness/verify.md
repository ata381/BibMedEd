# Verification Matrix

Run only the rows your change touches. Commands are from the repo root and written for the maintainer's Windows machine (Git Bash, venv at `.venv`). On Linux, macOS or a cloud sandbox, replace `.venv/Scripts/python.exe` with `python` (after `pip install -e "bibmeded[dev,server]"`) and `.venv/Scripts/mkdocs.exe` with `mkdocs`.

| Area touched | Command | Pass bar |
|---|---|---|
| `bibmeded/bibmeded/**`, `bibmeded/tests/**` | `cd bibmeded && ../.venv/Scripts/python.exe -m pytest -q --cov=bibmeded --cov-report=term` | all pass, coverage ≥ 90% (baseline ~94%). If pytest hits PermissionError on the temp dir (sandbox), add `--basetemp=<your scratchpad>/pt` |
| single backend module | `cd bibmeded && ../.venv/Scripts/python.exe -m pytest -q tests/<file>.py` | all pass (fast loop; still run the full suite before reporting) |
| `bibmeded/frontend/**` | `cd bibmeded/frontend && npm run lint && npx tsc --noEmit && npm run build` | zero errors |
| frontend user flows / a11y | `cd bibmeded/frontend && npm run test:e2e` | all pass |
| frontend code that reads API response fields | compare every field the UI reads against the backend's actual return shape in `bibmeded/bibmeded/analysis/*.py` / routers, AND against `e2e/mock-api.ts` — mocks can share the UI's wrong assumption (PR #75 shipped `count` vs `pub_count`). Prefer a live unmocked run where available | every read field exists in the real response |
| `docs/**`, `mkdocs.yml` | `.venv/Scripts/mkdocs.exe build --strict` | no warnings |
| `alembic/**`, models | CI job "Migrations (Postgres)" — cannot run locally without Postgres; say so | note as skipped |
| Dockerfile / compose | `cd bibmeded && docker compose config -q` | exit 0 |

Never hit live external APIs in tests — use fixtures under `bibmeded/tests/fixtures/`.
