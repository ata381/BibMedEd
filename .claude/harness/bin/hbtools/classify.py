"""Classify a PR by login, head repository and body marker. Never by names in text."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from . import config, gh

PR_FIELDS = ",".join([
    "number", "title", "author", "headRefName", "headRefOid", "headRepository", "headRepositoryOwner",
    "isDraft", "createdAt", "body", "baseRefName", "mergeStateStatus", "mergeable", "statusCheckRollup",
    "files", "labels", "url", "reviews", "commits",
])


def fetch_pr(number: int) -> dict:
    return gh.run_json(["pr", "view", str(number), "--repo", config.REPO, "--json", PR_FIELDS])


def marker_of(body: str | None) -> tuple[str | None, str | None]:
    match = re.search(config.MARKER_RE, body or "")
    if not match:
        return None, None
    return match.group(1), match.group(2)


def age_hours(created_at: str, now: datetime | None = None) -> float:
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    now = now or datetime.now(timezone.utc)
    return (now - created).total_seconds() / 3600


def classify(pr: dict, now: datetime | None = None) -> dict:
    login = (pr.get("author") or {}).get("login") or ""
    head_owner = (pr.get("headRepositoryOwner") or {}).get("login") or ""
    same_repo = head_owner == config.REPO.split("/")[0]
    branch = pr.get("headRefName") or ""
    role, marker_sha = marker_of(pr.get("body"))
    head_sha = pr.get("headRefOid") or ""
    info = {
        "number": pr.get("number"),
        "login": login,
        "head_repo_same": same_repo,
        "branch": branch,
        "head_sha": head_sha,
        "draft": bool(pr.get("isDraft")),
        "age_hours": round(age_hours(pr["createdAt"], now), 1) if pr.get("createdAt") else None,
        "marker_role": role,
        "marker_sha_matches": bool(marker_sha) and head_sha.startswith(marker_sha),
        "files": [f["path"] for f in pr.get("files") or []],
        "title": pr.get("title"),
    }
    if not same_repo:
        cls = "external"
    elif login == config.DEPENDABOT:
        cls = "dependabot"
    elif branch.startswith(config.AGENT_BRANCH_PREFIX):
        cls = "agent" if role and info["marker_sha_matches"] else "agent-unverified"
    elif login == config.OWNER:
        cls = "owner"
    elif login in config.DEVELOPERS:
        cls = "developer"
    else:
        cls = "external"
    info["class"] = cls
    return info


def summarize(info: dict) -> str:
    notes = []
    if info["draft"]:
        notes.append("draft")
    if info["class"] == "agent-unverified":
        notes.append("claude/ branch without a valid marker: treat as the owner's WIP, never merge")
    return f"PR #{info['number']} is {info['class']} (login {info['login']!r}, branch {info['branch']!r})" + (
        f"; {'; '.join(notes)}" if notes else "")
