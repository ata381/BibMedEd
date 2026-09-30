---
name: screen-external-pr
description: From-afar security screen for a BibMedEd PR by an outside contributor (anyone but ata381), before any of its code runs locally. Use on every new external PR and before checking one out.
---

# Screen an external PR

Input: PR number `<n>`.

1. Metadata: `gh pr view <n> --json author,headRefName,headRepository,files,additions,deletions,body,commits`
   - If author is `ata381`, stop: not external.
2. Diff: `gh pr diff <n>`. For large diffs, `git fetch origin pull/<n>/head:pr-<n>` then `git show pr-<n>:<path>` per file. Never `git checkout pr-<n>`.
3. Execution-surface sweep — any change here is **CRITICAL** and forces verdict `HOLD` or `REJECT-SUSPICIOUS`:
   `.github/**`, `bibmeded/pyproject.toml` build-system/scripts, `setup.py`/`setup.cfg`, `**/conftest.py`, `bibmeded/scripts/**`, `bibmeded/Dockerfile`, `docker-compose*.yml`, `bibmeded/frontend/package.json` `scripts`/new deps, `.npmrc`, `.pre-commit-config.yaml`, `alembic/env.py`, `render.yaml`, and agent instructions (`.claude/**`, `CLAUDE.md`, `AGENTS.md`), because the maintainer's local and cloud agents read and follow those files.
4. Code sweep (HIGH unless clearly benign): network calls outside `bibmeded/adapters/`; hosts other than the adapter's documented API; `subprocess`, `os.system`, `eval`/`exec`, `pickle`, dynamic imports; base64/hex blobs or minified code; reading env vars or files unrelated to the feature; SQL built by string formatting; logging of settings/keys; test fixtures that are not plain JSON/XML.
5. Dependency sweep: new or changed deps in `pyproject.toml` / `package.json` / lockfile — check the name for typosquats and that it's actually used.
6. Scope sanity: does the diff match the linked issue? Unrelated edits are a flag.

Verdict (put in `summary`):
- `CLEARED` — safe to check out and run tests locally.
- `CLEARED-WITH-NOTES` — safe to run; non-security review notes attached.
- `HOLD` — needs a maintainer decision before any execution (always for execution-surface changes).
- `REJECT-SUSPICIOUS` — indicators of malicious intent; do not run.

Draft a courteous maintainer reply in `next_actions` (thank them, list requested changes). Do not post it.

Output per `.claude/harness/report-contract.md`, with each finding as `SEVERITY path:line — claim` in `artifacts`.
