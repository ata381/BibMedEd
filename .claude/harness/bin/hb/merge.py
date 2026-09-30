"""merge-pr: every mechanical merge gate in one place. Refuses unless all pass, then squash-merges at the given SHA."""

from __future__ import annotations

from datetime import date, datetime, timezone

from . import classify, config, gh, paths

THREADS_QUERY = """
query($owner:String!,$name:String!,$number:Int!){
  repository(owner:$owner,name:$name){ pullRequest(number:$number){
    reviewThreads(first:100){ nodes{ isResolved resolvedBy{login}
      comments(first:1){ nodes{ author{login} createdAt } } } }
    reviews(first:100){ nodes{ author{login} state submittedAt } }
    commits(last:100){ nodes{ commit{ committedDate } } } } } }
"""

CLEARED = {"CLEARED", "CLEARED-WITH-NOTES"}


def fetch_threads(number: int) -> dict:
    owner, name = config.REPO.split("/")
    data = gh.graphql(THREADS_QUERY, {"owner": owner, "name": name, "number": number})
    return data["data"]["repository"]["pullRequest"]


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _check_states(pr: dict) -> dict[str, str]:
    states = {}
    for entry in pr.get("statusCheckRollup") or []:
        name = entry.get("name") or entry.get("context") or ""
        states[name] = (entry.get("conclusion") or entry.get("state") or "").upper()
    return states


def evaluate(pr: dict, info: dict, review: dict, state: dict, now: datetime | None = None, today: date | None = None) -> list[str]:
    """Return the list of failed gates (empty means mergeable)."""
    now = now or datetime.now(timezone.utc)
    today = today or now.date()
    fails: list[str] = []
    cls = info["class"]
    files = info["files"]
    number = str(info["number"])

    if cls == "agent-unverified":
        fails.append("class: claude/ branch without a valid marker (owner WIP or stale marker)")
    if (info.get("title") or "").lower().startswith(config.NEEDS_OWNER_TITLE_PREFIX):
        fails.append("title starts with needs-owner: the owner decides this PR")
    manifests = paths.hits(files, config.DEPENDENCY_MANIFESTS)
    if manifests and cls != "dependabot" and not (cls == "agent" and info["branch"].startswith("claude/release-")):
        fails.append("changes a dependency manifest (" + ", ".join(sorted({p for p, _ in manifests})) + "); only dependabot or the owner may")
    if info["draft"]:
        fails.append("draft PR")
    if any((lbl.get("name") or "").lower() == "wip" for lbl in pr.get("labels") or []):
        fails.append("label wip")
    if (pr.get("mergeStateStatus") or "").upper() != "CLEAN":
        fails.append(f"mergeStateStatus is {pr.get('mergeStateStatus')!r}, need CLEAN (checks, up to date, threads resolved)")

    states = _check_states(pr)
    for name in config.REQUIRED_CHECKS:
        if states.get(name) != "SUCCESS":
            fails.append(f"required check {name!r} is {states.get(name) or 'missing'}")
    if any(f.startswith(config.FRONTEND_PREFIX) for f in files) and states.get(config.FRONTEND_EXTRA_CHECK) != "SUCCESS":
        fails.append(f"frontend change needs {config.FRONTEND_EXTRA_CHECK!r} green")

    threads = review.get("reviewThreads", {}).get("nodes") or []
    unresolved = [t for t in threads if not t.get("isResolved")]
    if unresolved:
        fails.append(f"{len(unresolved)} unresolved review thread(s)")
    reviews = review.get("reviews", {}).get("nodes") or []
    codex_seen = any((r.get("author") or {}).get("login") == config.CODEX_LOGIN for r in reviews) or any(
        ((t.get("comments") or {}).get("nodes") or [{}])[0].get("author", {}).get("login") == config.CODEX_LOGIN for t in threads)
    age = info.get("age_hours") or 0.0

    if cls == "agent":
        if not codex_seen:
            fails.append("agent PR needs a Codex review before merging")
        if age < config.AGENT_LATER_RUN_HOURS:
            fails.append(f"agent PR is {age:.1f} h old; merge only on a later run (≥ {config.AGENT_LATER_RUN_HOURS} h)")
        commit_dates = [_ts(c["commit"]["committedDate"]) for c in (review.get("commits", {}).get("nodes") or []) if c.get("commit")]
        for t in threads:
            first = ((t.get("comments") or {}).get("nodes") or [None])[0]
            if t.get("isResolved") and first and first.get("author", {}).get("login") == config.CODEX_LOGIN:
                opened = _ts(first["createdAt"])
                if not any(c > opened for c in commit_dates):
                    fails.append("a Codex thread on an agent PR was resolved without a later fix commit")
                    break
    elif not codex_seen and age < config.CODEX_GRACE_HOURS:
        fails.append(f"no Codex review yet and PR is {age:.1f} h old; wait {config.CODEX_GRACE_HOURS} h")

    if cls == "external":
        rec = (state.get("screened") or {}).get(number)
        if not rec:
            fails.append("external PR has no recorded screen verdict")
        elif not info["head_sha"].startswith(rec["sha"]) and not rec["sha"].startswith(info["head_sha"]):
            fails.append(f"screen verdict is for {rec['sha'][:10]}, head is {info['head_sha'][:10]}; re-screen")
        elif rec["verdict"] not in CLEARED:
            fails.append(f"screen verdict is {rec['verdict']}")

    if cls == "dependabot" and age < config.DEPENDABOT_COOLDOWN_DAYS * 24:
        fails.append(f"dependabot cooldown: PR is {age / 24:.1f} days old, need {config.DEPENDABOT_COOLDOWN_DAYS}")

    denied = paths.hits(files, config.NEVER_MERGE_PATHS)
    if denied:
        release_prep = cls == "agent" and info["branch"].startswith("claude/release-") and not paths.all_within(files, config.RELEASE_PREP_ALLOWED)
        actions_bump = (cls == "dependabot" and (info.get("title") or "").startswith(config.DEPENDABOT_WORKFLOW_BUMP_PREFIX)
                        and not paths.all_within(files, (".github/workflows/**",)))
        if not (release_prep or actions_bump):
            fails.append("touches never-merge path(s): " + ", ".join(sorted({p for p, _ in denied})[:6]))

    if cls == "agent" and info.get("marker_role") == "worker" and today <= date.fromisoformat(config.WORKER_ALLOWLIST_UNTIL):
        outside = paths.all_within(files, config.WORKER_ALLOWLIST)
        approved = any((r.get("author") or {}).get("login") in config.TRUSTED and r.get("state") == "APPROVED" for r in reviews)
        if outside and not approved:
            fails.append("worker PR touches paths outside the sprint allowlist and has no approval from ata381 or MugeBakiryol: "
                         + ", ".join(outside[:6]))
    return fails


def perform(number: int, sha: str) -> str:
    res = gh.run(["pr", "merge", str(number), "--repo", config.REPO, "--squash", "--match-head-commit", sha])
    return (res.stdout or res.stderr).strip()
