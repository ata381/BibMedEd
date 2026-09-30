# BibMedEd 0.4.0 release checklist

Maintainer-side checklist for the first PyPI release. Excluded from the public MkDocs build. Every networked action below requires an explicit maintainer go-ahead. See also [`pypi-release.md`](pypi-release.md).

0.4.0 highlights: `pip install bibmeded` CLI, package rename `app` -> `bibmeded` (breaking), frontend redesign, `BIBMEDED_READ_ONLY` mode and local demo, SQLAlchemy 2.1 fix, new CLI commands from first-time contributors. A hosted public demo is deliberately not part of this release.

## Before tagging

1. Confirm the one-time PyPI setup in `pypi-release.md` is done: pending publisher for `bibmeded` (owner `ata381`, repo `BibMedEd`, workflow `release.yml`, environment `pypi`), and the GitHub `pypi` environment has a required reviewer and a `v*` tag restriction.
2. Merge the release-preparation PR and confirm CI is green on the exact merge commit of `master`.
3. Confirm version metadata agrees at that commit: `bibmeded/pyproject.toml`, `CITATION.cff` (`version`, `date-released`), the `CHANGELOG.md` 0.4.0 heading, and the OpenAPI `info.version`.

## Release sequence

1. Create an annotated tag `v0.4.0` on the full `master` merge commit SHA, verify the tag object, and push it.
2. Publish a GitHub release for `v0.4.0` using the 0.4.0 section of `CHANGELOG.md`. The workflow checks that the tag equals `v` plus the pyproject version.
3. Watch `release.yml`: the test gate, sdist and wheel build, and `twine check --strict` must pass. Confirm the wheel is `bibmeded-0.4.0-py3-none-any.whl`.
4. Approve the `pypi` environment deployment so the upload proceeds.
5. Verify in a clean venv: `pip install bibmeded==0.4.0 && bibmeded --version && bibmeded sources`.
6. Verify the release links: GitHub release, PyPI project page and README badge, GitHub Pages, and the Zenodo version record and citation metadata.

PyPI versions are immutable. If the release is bad, yank it and publish 0.4.1.

## Approval gates

- [ ] Push the release-preparation commit and merge the PR
- [ ] Push the `v0.4.0` tag
- [ ] Publish the `v0.4.0` GitHub release
- [ ] Approve the `pypi` environment deployment
- [ ] Post any announcement (Discussion, social) after PyPI verification
