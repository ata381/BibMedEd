"""close-issue, floodgate, heartbeat, commands: the smaller gated actions."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from . import config, gh

LINKED_QUERY = """
query($owner:String!,$name:String!,$number:Int!){
  repository(owner:$owner,name:$name){ issue(number:$number){
    author{login} state title
    labels(first:20){ nodes{ name } }
    timelineItems(first:100, itemTypes:[CROSS_REFERENCED_EVENT]){ nodes{
      ... on CrossReferencedEvent { source{ ... on PullRequest { number state } } } } } } } }
"""
CLOSE_REASONS = {"duplicate": "not planned", "spam": "not planned", "not-planned": "not planned"}
COMMAND_RE = re.compile(r"^/(pause|resume|approve|reject)(?:\s+(E-\d{3,}))?\s*$", re.M)


def issue_facts(number: int) -> dict:
    owner, name = config.REPO.split("/")
    data = gh.graphql(LINKED_QUERY, {"owner": owner, "name": name, "number": number})
    issue = data["data"]["repository"]["issue"]
    open_prs = sorted({n["source"]["number"] for n in issue["timelineItems"]["nodes"]
                       if (n.get("source") or {}).get("state") == "OPEN"})
    return {
        "author": (issue.get("author") or {}).get("login") or "",
        "state": issue.get("state"),
        "title": issue.get("title"),
        "labels": [l["name"] for l in issue["labels"]["nodes"]],
        "open_linked_prs": open_prs,
    }


def close_gates(facts: dict, reason: str, comment: str, closed_this_run: int) -> list[str]:
    fails = []
    if reason not in CLOSE_REASONS:
        fails.append(f"reason must be one of {sorted(CLOSE_REASONS)}")
    if facts["author"] in config.TRUSTED:
        fails.append(f"issue by trusted login {facts['author']!r}: never closed by an agent")
    if facts["state"] != "OPEN":
        fails.append("issue is not open")
    if facts["open_linked_prs"]:
        fails.append(f"issue has open linked PR(s) {facts['open_linked_prs']}")
    if "maintainer-agent" in facts["labels"]:
        fails.append("inbox issue is never closed")
    if closed_this_run >= config.CLOSE_CAP_PER_RUN:
        fails.append(f"closure cap {config.CLOSE_CAP_PER_RUN} per run reached")
    if len(comment.strip()) < 40:
        fails.append("comment too short to explain a closure")
    return fails


def with_footer(comment: str) -> str:
    return comment.rstrip() + ("\n\n" + config.FOOTER if config.FOOTER not in comment else "")


def perform_close(number: int, reason: str, comment: str) -> None:
    gh.run(["issue", "comment", str(number), "--repo", config.REPO, "--body", with_footer(comment)])
    gh.run(["issue", "close", str(number), "--repo", config.REPO, "--reason", CLOSE_REASONS[reason]])


def flood_counts(since: str | None) -> dict:
    prs = gh.run_json(["pr", "list", "--repo", config.REPO, "--state", "open", "--limit", "100", "--json", "createdAt,author"]) or []
    issues = gh.run_json(["issue", "list", "--repo", config.REPO, "--state", "open", "--limit", "100", "--json", "createdAt,author"]) or []

    def newer(items):
        if not since:
            return items
        cutoff = datetime.fromisoformat(since.replace("Z", "+00:00"))
        return [i for i in items if datetime.fromisoformat(i["createdAt"].replace("Z", "+00:00")) > cutoff]

    new_prs = [p for p in newer(prs) if (p.get("author") or {}).get("login") not in config.TRUSTED]
    new_issues = [i for i in newer(issues) if (i.get("author") or {}).get("login") not in config.TRUSTED]
    mode = "triage-only" if (len(new_prs) > config.FLOOD_MAX_NEW_PRS or len(new_issues) > config.FLOOD_MAX_NEW_ISSUES) else "normal"
    return {"new_prs": len(new_prs), "new_issues": len(new_issues), "mode": mode, "since": since}


def heartbeat_line(role: str, status: str, closes: int, reverts: int, holds: int, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return (f"{config.HEARTBEAT_PREFIX} {now.strftime('%Y-%m-%dT%H:%MZ')} by {role} | {status} | "
            f"closes:{closes} reverts:{reverts} holds:{holds}")


def replace_heartbeat(body: str, line: str) -> str:
    lines = body.splitlines()
    if lines and lines[0].startswith(config.HEARTBEAT_PREFIX):
        lines[0] = line
    else:
        lines = [line, ""] + lines
    return "\n".join(lines) + ("\n" if body.endswith("\n") else "")


def write_heartbeat(line: str) -> None:
    issue = gh.api(f"repos/{config.REPO}/issues/{config.INBOX_ISSUE}")
    new_body = replace_heartbeat(issue.get("body") or "", line)
    gh.api(f"repos/{config.REPO}/issues/{config.INBOX_ISSUE}", method="PATCH", raw_input=json.dumps({"body": new_body}))


def is_agent_output(body: str) -> bool:
    return config.FOOTER in body or re.search(config.MARKER_RE, body) is not None


def owner_commands(since: str | None) -> list[dict]:
    """Commands are lines in #102 comments by the owner that carry neither footer nor marker."""
    comments = gh.api(f"repos/{config.REPO}/issues/{config.INBOX_ISSUE}/comments?per_page=100", paginate=True) or []
    if isinstance(comments, dict):
        comments = [comments]
    cutoff = datetime.fromisoformat(since.replace("Z", "+00:00")) if since else None
    found = []
    for c in comments:
        if (c.get("user") or {}).get("login") != config.OWNER:
            continue
        body = c.get("body") or ""
        if is_agent_output(body):
            continue
        created = datetime.fromisoformat(c["created_at"].replace("Z", "+00:00"))
        if cutoff and created <= cutoff:
            continue
        for m in COMMAND_RE.finditer(body):
            found.append({"command": m.group(1), "id": m.group(2), "comment_url": c.get("html_url"), "at": c["created_at"]})
    return found
