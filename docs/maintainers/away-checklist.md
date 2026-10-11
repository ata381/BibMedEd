# Maintainer away checklist

Maintainer checklist. This folder is excluded from the public MkDocs build (`exclude_docs` in `mkdocs.yml`). The response-time targets contributors are promised are in [`CONTRIBUTING.md`](../../CONTRIBUTING.md#response-times); this page is how the two maintainers keep them when one is away.

## Weekly triage

The two maintainers alternate a 30-minute Monday triage: Dependabot PRs, CI approvals, new claims, "Update branch" clicks, and stale claims.

## Before leaving

1. Post `away until <date>, @MugeBakiryol covers` (or the reverse, `@ata381 covers`) on each open external PR.
2. Set your GitHub status to busy with the same text.
3. Disable auto-merge on any of your own PRs that nobody has reviewed.

## Who can do what

The covering maintainer, with write access, can:

- approve CI runs for first-time contributors;
- review and merge contributor PRs;
- triage and label issues and PRs;
- click "Update branch" on a PR that has fallen behind `master`;
- run an on-demand agent review from the diff.

Only the owner can:

- approve PyPI releases;
- change repository settings;
- see private vulnerability reports;
- change `LICENSE`, `CITATION.cff` authorship, `render.yaml` service plans, or the agent instructions (`CLAUDE.md`, `AGENTS.md`).

The authoritative list of owner-only decisions is the "Trusted developers" section of [`CLAUDE.md`](../../CLAUDE.md). Anything on it waits for the owner's return.

## When no local machine works

- Dependabot PRs can be reviewed and merged from the GitHub web UI once CI is green.
- For anything that needs a checkout, open a GitHub Codespace on the branch. For an external PR, read the diff first, as the security screen in `CLAUDE.md` requires, before running anything in it.

## On return

1. The Monday triage list first: CI approvals, dependency PRs, claims.
2. Then reviews, oldest first.
3. Then your own PRs.
