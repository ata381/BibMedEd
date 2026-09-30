---
name: ship-branch
description: Manager's merge-readiness gate for a BibMedEd branch produced by a subagent. Rebases a copy on master, runs the verification matrix, gets an independent review, and hands the maintainer a go/no-go. Never merges or pushes without explicit maintainer approval.
---

# Ship a branch

Input: branch name.

1. Read the producing agent's report. Distrust claims until re-verified.
2. `git fetch origin && git log --oneline master..<branch>` — check commit messages are conventional and carry Co-Authored-By.
3. Conflict check: `git merge-tree --write-tree master <branch>`; if conflicts, send the branch back to its author agent (SendMessage) to rebase — don't resolve silently.
4. Protected files: `git diff --name-only master...<branch>` must not include `LICENSE`, `render.yaml`, or authorship in `CITATION.cff`/`pyproject.toml` unless the maintainer approved it.
5. Re-run the relevant `.claude/harness/verify.md` rows yourself in the branch's worktree.
6. Spawn `bibmeded-reviewer` (or `bibmeded-security-screener` for security-sensitive scope) on the branch. Route CRITICAL/HIGH back to the author agent; max 2 fix rounds, then escalate to the maintainer.
7. After the PR is open: master requires **all review conversations resolved** (plus strict up-to-date + required checks). Codex (`chatgpt-codex-connector`) and CodeQL post review threads that silently hold auto-merge in `BLOCKED`. Read every unresolved thread (GraphQL `reviewThreads`); fix real findings (P1 = must-fix), reply with the fix commit, and only then resolve; for deferrals file an issue and link it in the reply.
8. Hand the maintainer: branch, what it does in 2–3 lines, verification table, open risks, and the exact commands to push + open the PR. Push/PR only after they say go.
