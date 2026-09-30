"""The agents' only memory: one comment on the inbox issue carrying STATE_MARKER and a JSON block.

Enums and ids only. Read validates; update re-reads, checks the comment's updated_at (compare-and-swap),
merges top-level keys, prunes, validates and writes.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone

from . import config, gh

ID_RE = re.compile(r"^E-\d{3,}$")
ITEM_RE = re.compile(r"^(#\d+|PR #\d+|v\d+\.\d+\.\d+|[A-Za-z0-9._/-]{1,60})$")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?Z)?$")
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
WEEK_RE = re.compile(r"^\d{4}-W\d{2}$")


def empty_state() -> dict:
    return {
        "version": 1,
        "mode": "normal",
        "last_run": {"maintainer": None, "worker": None},
        "escalations": [],
        "screened": {},
        "release": {"state": "idle", "version": None, "ref": None},
        "metrics": [],
    }


class StateError(ValueError):
    pass


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise StateError(msg)


def validate(state: dict) -> None:
    _check(isinstance(state, dict), "state is not an object")
    _check(state.get("version") == 1, "unknown state version")
    _check(state.get("mode") in config.MODES, f"mode must be one of {config.MODES}")
    last_run = state.get("last_run")
    _check(isinstance(last_run, dict), "last_run must be an object")
    for role in config.ROLES:
        value = last_run.get(role)
        _check(value is None or (isinstance(value, str) and TS_RE.match(value)), f"last_run.{role} must be a UTC timestamp or null")
    esc = state.get("escalations")
    _check(isinstance(esc, list), "escalations must be a list")
    seen = set()
    for item in esc:
        _check(isinstance(item, dict), "escalation must be an object")
        _check(set(item) == {"id", "item", "kind", "status", "opened"}, f"escalation keys wrong: {sorted(item)}")
        _check(bool(ID_RE.match(item["id"])), f"bad escalation id {item['id']!r}")
        _check(item["id"] not in seen, f"duplicate escalation id {item['id']}")
        seen.add(item["id"])
        _check(bool(ITEM_RE.match(str(item["item"]))), f"bad escalation item {item['item']!r}")
        _check(item["kind"] in config.ESCALATION_KINDS, f"bad escalation kind {item['kind']!r}")
        _check(item["status"] in config.ESCALATION_STATUSES, f"bad escalation status {item['status']!r}")
        _check(bool(TS_RE.match(str(item["opened"]))), f"bad escalation date {item['opened']!r}")
    screened = state.get("screened")
    _check(isinstance(screened, dict), "screened must be an object")
    for number, rec in screened.items():
        _check(number.isdigit(), f"screened key {number!r} is not a PR number")
        _check(isinstance(rec, dict) and set(rec) == {"sha", "verdict", "at"}, f"screened[{number}] keys wrong")
        _check(bool(SHA_RE.match(rec["sha"])), f"screened[{number}].sha invalid")
        _check(rec["verdict"] in config.VERDICTS, f"screened[{number}].verdict invalid")
        _check(bool(TS_RE.match(rec["at"])), f"screened[{number}].at invalid")
    rel = state.get("release")
    _check(isinstance(rel, dict) and set(rel) == {"state", "version", "ref"}, "release keys wrong")
    _check(rel["state"] in config.RELEASE_STATES, f"bad release state {rel['state']!r}")
    _check(rel["version"] is None or re.match(r"^\d+\.\d+\.\d+$", rel["version"]), "release.version invalid")
    _check(rel["ref"] is None or re.match(r"^#\d+$", rel["ref"]), "release.ref invalid")
    metrics = state.get("metrics")
    _check(isinstance(metrics, list) and len(metrics) <= config.METRICS_WEEKS_KEPT, "metrics must be a list of at most 8 weeks")
    for row in metrics:
        _check(isinstance(row, dict) and WEEK_RE.match(str(row.get("week", ""))), "metrics row needs an ISO week")
        for key, value in row.items():
            _check(key == "week" or isinstance(value, (int, float)) or value is None, f"metrics.{key} must be numeric or null")
    _check(set(state) <= {"version", "mode", "last_run", "escalations", "screened", "release", "metrics"}, "unknown top-level key")


def render(state: dict) -> str:
    body = json.dumps(state, indent=2, sort_keys=True)
    return f"{config.STATE_MARKER}\nAgent state. Machine-edited; do not edit by hand.\n\n```json\n{body}\n```\n"


def parse(body: str) -> dict:
    match = re.search(r"```json\s*(\{.*?\})\s*```", body, re.S)
    _check(match is not None, "no JSON block in state comment")
    try:
        state = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise StateError(f"state JSON invalid: {exc}") from exc
    validate(state)
    return state


def _find_comment() -> dict | None:
    comments = gh.api(f"repos/{config.REPO}/issues/{config.INBOX_ISSUE}/comments?per_page=100", paginate=True) or []
    if isinstance(comments, dict):
        comments = [comments]
    for comment in comments:
        if config.STATE_MARKER in (comment.get("body") or ""):
            return comment
    return None


def read() -> tuple[dict, dict]:
    """Return (meta, state). meta has id and updated_at."""
    comment = _find_comment()
    _check(comment is not None, "state comment not found; run `hb state init`")
    state = parse(comment["body"])
    return {"id": comment["id"], "updated_at": comment["updated_at"]}, state


def init(dry_run: bool = False) -> dict:
    if _find_comment() is not None:
        raise StateError("state comment already exists")
    state = empty_state()
    if dry_run:
        return state
    gh.api(f"repos/{config.REPO}/issues/{config.INBOX_ISSUE}/comments", method="POST",
           raw_input=json.dumps({"body": render(state)}))
    return state


def prune(state: dict, open_prs: set[str] | None) -> dict:
    new = deepcopy(state)
    if open_prs is not None:
        new["screened"] = {k: v for k, v in new["screened"].items() if k in open_prs}
    new["metrics"] = sorted(new["metrics"], key=lambda r: r["week"])[-config.METRICS_WEEKS_KEPT:]
    return new


def merge_patch(state: dict, patch: dict) -> dict:
    new = deepcopy(state)
    for key, value in patch.items():
        if key == "escalations":
            by_id = {e["id"]: e for e in new["escalations"]}
            for item in value:
                by_id[item["id"]] = item
            new["escalations"] = list(by_id.values())
        elif key == "screened":
            new["screened"].update(value)
        elif key in ("last_run", "release"):
            new[key] = {**new[key], **value}
        elif key == "metrics":
            by_week = {r["week"]: r for r in new["metrics"]}
            for row in value:
                by_week[row["week"]] = row
            new["metrics"] = list(by_week.values())
        else:
            new[key] = value
    return new


def update(patch: dict, expect_updated_at: str, open_prs: set[str] | None = None, dry_run: bool = False) -> tuple[dict, dict]:
    meta, current = read()
    _check(meta["updated_at"] == expect_updated_at,
           f"state changed since read (expected {expect_updated_at}, now {meta['updated_at']}); re-read and retry once")
    new = prune(merge_patch(current, patch), open_prs)
    validate(new)
    if dry_run:
        return meta, new
    updated = gh.api(f"repos/{config.REPO}/issues/comments/{meta['id']}", method="PATCH",
                     raw_input=json.dumps({"body": render(new)}))
    return {"id": meta["id"], "updated_at": (updated or {}).get("updated_at", meta["updated_at"])}, new


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
