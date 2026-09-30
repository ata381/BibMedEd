# Report Contract

> Cloud routines run under `.claude/harness/constitution.md` and their role file; the never-post/push/merge limits in this file apply to local supervised sessions.

Every BibMedEd subagent ends its run with exactly this block, so the manager can parse results without rereading transcripts.

```yaml
status: success | warning | error | blocked
summary: <one line — what changed or what was found>
branch: <branch name or "none">
commits: [<short sha> <subject>, ...]
verification:
  - cmd: <exact command run>
    result: pass | fail | skipped
    detail: <counts, coverage %, or first failing line>
artifacts: [<file paths, issue/PR numbers, screenshot paths>]
next_actions: [<concrete follow-ups the manager or a human should take>]
needs_human: [<decisions or outward actions only a maintainer may take>]
```

Rules
- `status: success` requires every listed verification to be `pass`. Anything skipped or failing ⇒ `warning` or `error`, stated plainly.
- Never claim a check ran if it didn't. Paste the real failing line into `detail`.
- `blocked` = hit a stop condition (see below); explain in `summary`, put the unblock step in `needs_human`.

Stop conditions (stop and report `blocked`, don't improvise around them)
- Same failure after 2 fix attempts with the same root cause.
- A change would touch `LICENSE`, `CITATION.cff` authorship, or `render.yaml` service plans.
- A change needs a heavyweight or paid dependency.
- Anything outward-facing: push, PR, issue/comment post, merge, release, publish.
- Executing code from an external contributor's PR before it passed `screen-external-pr`.
