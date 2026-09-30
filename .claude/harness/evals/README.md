# Harness evals

Two layers, both required before a harness PR is merged.

1. **Gate tests** (mechanical): `python -m pytest .claude/harness/bin/tests -q`. They pin the merge, close, state, classification and path gates against recorded `gh` shapes. A gate change without a test change is a review finding.
2. **Replay cases** (judgement): `cases.json` holds real situations from this repo's history with the decision the maintainer role must reach. Before opening a harness PR, replay them in a local Claude Code session: give the session the constitution, the role file and one case's `input`, ask for the decision and the exact `hb` calls, and compare with `expected`. Paste the table (case id, pass/fail, one line) into the PR body. A failed case blocks the PR.

Adding a case: copy a real event (issue text summarised, never pasted verbatim if it came from an outsider), state the repo facts the agent would see, and write the expected decision as the tool calls it should make and the ones it must not make.
