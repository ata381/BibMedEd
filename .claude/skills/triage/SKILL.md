---
name: triage
description: Hacktoberfest / community triage pass for BibMedEd — new issues, comments, claims, and PRs since the last pass. Produces a digest and drafted replies; never posts. Use on a recurring loop or on demand.
---

# Triage pass

State file: `.claude/state/triage.json` → `{"last_run": "<ISO8601>", "seen": {"issue:<n>": "<updatedAt>", "pr:<n>": "<updatedAt>"}}`. Create it if missing with `last_run` = 7 days ago. Only report items whose `updatedAt` is newer than `seen`.

Gather (read-only)
- `gh issue list -R ata381/BibMedEd --state open --limit 100 --json number,title,labels,assignees,updatedAt,author,comments`
- `gh pr list -R ata381/BibMedEd --state open --limit 50 --json number,title,author,updatedAt,isDraft,labels,statusCheckRollup,reviewDecision,closingIssuesReferences`
- For changed items: `gh issue view <n> --comments` / `gh pr view <n> --comments`.

Classify each changed item
| Signal | Action to propose |
|---|---|
| Comment asking to claim an unassigned issue | Assign + welcome reply (link `CONTRIBUTING.md`, the adapter guide if adapter, and the acceptance criteria) |
| Claim on an already-assigned issue | Polite reply naming the current owner; suggest a similar open issue |
| Assignee silent ≥ 14 days | Friendly check-in; if already checked in 7+ days ago with no reply, propose unassigning (per `GOOD_FIRST_ISSUES.md`) |
| New external PR | Run `screen-external-pr` via the bibmeded-security-screener agent before anything else; report its verdict |
| PR from Dependabot | Report CI status; flag majors (e.g. TypeScript, Next, React) for a human |
| External PR that is CLEARED and meets acceptance criteria | Propose merge once CI is green. Requested changes: if ≥ ~20 lines or design-level, draft a review asking the contributor; if < ~20 lines, propose "merge, then maintainer follow-up commit" (credit them) |
| PR with failing CI | Summarise first failing job + line; draft a helpful reply |
| Merged external PR | Propose a CHANGELOG "Unreleased" credit line (`@handle`) and a thank-you comment |
| Spam / low-effort PR (whitespace, README typo churn) | Propose `invalid` + `spam` per Hacktoberfest rules; draft neutral reply |
| New issue from a user | Reproduce-ability check, propose labels (`bug`/`enhancement`/`area/*`), draft reply |

Promise to keep: acknowledge claims within 3 working days (`GOOD_FIRST_ISSUES.md`). Flag anything older than 2 working days without a maintainer response as **URGENT**.

Output
1. Update the state file.
2. Report per `.claude/harness/report-contract.md`. `needs_human` = ordered list of `ACTION #n — exact gh command — drafted reply text`, URGENT first. If nothing changed: `status: success`, `summary: no new activity`.
