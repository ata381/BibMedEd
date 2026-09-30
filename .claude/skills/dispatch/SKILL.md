---
name: dispatch
description: Manager routing policy for BibMedEd — which agent and model gets which work, how to brief them, and how to run the loop. Load at the start of any multi-agent session on this repo.
---

# Dispatch policy

> Cloud routines run under `.claude/harness/constitution.md` and their role file; the never-post/push/merge limits in this file apply to local supervised sessions.

| Work | Agent | Model | Isolation |
|---|---|---|---|
| Scoped issue, bug, adapter, docs, CLI, routine UI | `bibmeded-implementer` | sonnet | worktree |
| Security-sensitive build (auth-less exposure, demo/read-only, HTTP clients, exports of user data, CI) | `bibmeded-implementer` with `model: opus` override | opus | worktree |
| Branch review | `bibmeded-reviewer` | sonnet | none |
| External PR / security review | `bibmeded-security-screener` | opus | none |
| Community triage | `bibmeded-triager` | sonnet | none |
| Full visual/UX redesign, design system, novel viz | `bibmeded-designer` | **fable — at most one running at a time** | worktree |
| Research / drafting (no code) | general-purpose | sonnet | none |

Fable gate: only if the scope spans multiple routes *and* needs original design judgement. Otherwise implementer.

Brief template (every dispatch)
- Goal and why it matters (traction, safety, contributor UX).
- Exact scope in / out; files other agents are touching right now (avoid conflicts).
- Acceptance criteria and which `verify.md` rows apply.
- Branch name and the Co-Authored-By line for that model.
- "Never push, PR, post, or merge. Finish with `.claude/harness/report-contract.md`."

Loop
1. Dispatch independent streams in parallel; serialise streams that touch the same files (e.g. frontend redesign ⟂ frontend dependency bumps).
2. On each report: run `ship-branch`. Record outcome in `.claude/state/manager-log.md` (date, branch, agent/model, status, retries).
3. Failure modes to watch: same root cause twice ⇒ stop and escalate; an agent exceeding its scope ⇒ reject and re-brief narrower.
4. Anything outward-facing waits for the maintainer.

Contribution merge policy (maintainer, 2026-09-30): merge every well-done outside contribution once it passes `screen-external-pr` and CI. Needed changes ≥ ~20 lines or design-level → ask the contributor in a review. Smaller → merge, then a `bibmeded-implementer` follow-up PR crediting them.
