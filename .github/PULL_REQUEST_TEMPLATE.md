<!-- Thanks for contributing to BibMedEd.

Three things that are normal here:
- CI on a first PR may wait for a maintainer to approve the run.
- You do not need to rebase after every merge to master. A maintainer will update your branch.
- Do not edit CHANGELOG.md. Maintainers add the entry at release time.
-->

## Summary

<!-- One or two sentences: what this PR changes and why. -->

## Type of change

- [ ] Bug fix
- [ ] New adapter
- [ ] New analysis module
- [ ] Docs / examples
- [ ] Refactor / chore
- [ ] Feature / CLI enhancement

## Checklist

- [ ] `pytest` passes locally (`cd bibmeded && pytest -q`)
- [ ] Touched code paths have tests
- [ ] If adding an adapter: implements `search` and `fetch`; has a clear `display_name` / methodology label; is auto-discovered by the registry; has fixture-based tests
- [ ] Docs updated (`docs/` and / or README) if user-visible behaviour changed
- [ ] No secrets, API keys, or personal data committed

## Related issues

Closes #
