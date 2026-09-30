# Publishing to PyPI

Maintainer checklist. This folder is excluded from the public MkDocs build (`exclude_docs` in `mkdocs.yml`). Releases are published by `.github/workflows/release.yml` using PyPI Trusted Publishing, so no API token is stored anywhere.

## One-time setup

1. Create a PyPI account (with 2FA) at <https://pypi.org> if you do not have one.
2. Register a **pending publisher** at <https://pypi.org/manage/account/publishing/> (this reserves the name `bibmeded` on first publish):
   - PyPI project name: `bibmeded`
   - Owner: `ata381`
   - Repository name: `BibMedEd`
   - Workflow name: `release.yml`
   - Environment name: `pypi`
3. In GitHub, go to Settings, Environments, create an environment named `pypi`. Add yourself as a required reviewer so every publish needs a manual approval, and restrict deployment to tags matching `v*`.
4. Optional but recommended: repeat step 2 on <https://test.pypi.org> and dry-run a pre-release first.

## Per-release steps

0. Tag only from a green `master` (CI passing on the exact commit). The release workflow re-runs the backend test suite on the tagged commit and blocks the build and publish jobs if it fails, but it is a last gate, not a substitute for CI. Make sure the `pypi` environment has a required reviewer configured (one-time step 3) so nothing uploads without a human approval.
1. Bump `version` in `bibmeded/pyproject.toml`, move the `CHANGELOG.md` entries under the new version, and merge to `master`.
2. Create an annotated tag `vX.Y.Z` on the merge commit and publish a GitHub release for it.
3. The workflow verifies the tag equals `v` plus the pyproject version, builds the sdist and wheel, runs `twine check --strict`, then waits for `pypi` environment approval and uploads.
4. Verify in a clean venv: `pip install bibmeded==X.Y.Z && bibmeded --help`.

PyPI versions are immutable. If a release is bad, yank it and publish a new patch version.
