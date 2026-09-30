"""hb: the gated harness tools for BibMedEd's cloud routines.

Usage: python .claude/harness/bin/hb.py <command> [options]
Commands: doctor, commands, state (read|init|update), classify-pr, screen-paths, merge-pr, close-issue, floodgate, heartbeat.
Every command prints one JSON report {status, summary, next_actions, artifacts, data} and exits 0 done, 1 refused, 2 error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hbtools import classify, config, doctor, gh, issues, merge, out, paths, state  # noqa: E402


def cmd_doctor(a) -> int:
    rep = doctor.run(a.expect_login, not a.no_network)
    if rep["stop"]:
        return out.emit(out.error("stop: " + "; ".join(rep["stops"]), data=rep["facts"], next_actions=["do nothing on GitHub", "write the final message with this reason"]))
    return out.emit(out.done("ok to proceed", data=rep["facts"]))


def cmd_commands(a) -> int:
    cmds = issues.owner_commands(a.since)
    return out.emit(out.done(f"{len(cmds)} owner command(s) since {a.since or 'the beginning'}", data={"commands": cmds}))


def cmd_state(a) -> int:
    try:
        if a.action == "init":
            st = state.init(dry_run=a.dry_run)
            return out.emit((out.dry_run if a.dry_run else out.done)("state comment initialised", data={"state": st}))
        if a.action == "read":
            meta, st = state.read()
            return out.emit(out.done("state read", data={"meta": meta, "state": st}))
        patch = json.loads(Path(a.patch_file).read_text(encoding="utf-8")) if a.patch_file else json.loads(a.patch or "{}")
        open_prs = set(a.open_prs.split(",")) if a.open_prs else None
        meta, st = state.update(patch, a.expect_updated_at, open_prs=open_prs, dry_run=a.dry_run)
        return out.emit((out.dry_run if a.dry_run else out.done)("state updated", data={"meta": meta, "state": st}))
    except state.StateError as exc:
        return out.emit(out.error(f"state: {exc}", next_actions=["re-read once; on a second failure run health and escalate only"]))


def cmd_classify(a) -> int:
    pr = classify.fetch_pr(a.number)
    info = classify.classify(pr)
    return out.emit(out.done(classify.summarize(info), data=info))


def cmd_screen_paths(a) -> int:
    pr = classify.fetch_pr(a.number)
    files = [f["path"] for f in pr.get("files") or []]
    hits = paths.hits(files, config.CRITICAL_PATHS)
    floor = "HOLD" if hits else None
    summary = (f"{len(hits)} CRITICAL path(s) touched; verdict floor HOLD" if hits else "no CRITICAL paths touched")
    return out.emit(out.done(summary, data={"files": files, "critical": [{"path": p, "rule": r} for p, r in hits], "verdict_floor": floor},
                             next_actions=(["post the neutral comment", "escalate kind: security with counts only"] if hits else [])))


def cmd_merge(a) -> int:
    pr = classify.fetch_pr(a.number)
    info = classify.classify(pr)
    review = merge.fetch_threads(a.number)
    try:
        _, st = state.read()
    except state.StateError as exc:
        return out.emit(out.error(f"state unreadable, refusing to merge: {exc}"))
    if not info["head_sha"].startswith(a.sha):
        return out.emit(out.refused(f"head is {info['head_sha'][:10]}, you passed {a.sha[:10]}; re-review the current head", data=info))
    fails = merge.evaluate(pr, info, review, st)
    if fails:
        return out.emit(out.refused("gate(s) failed: " + " | ".join(fails), data={"class": info["class"], "gates_failed": fails},
                                    next_actions=["list under blocked:", "do not retry this run"]))
    if a.dry_run:
        return out.emit(out.dry_run(f"would squash-merge PR #{a.number} at {info['head_sha'][:10]} ({info['class']})", data=info))
    result = merge.perform(a.number, info["head_sha"])
    return out.emit(out.done(f"merged PR #{a.number} at {info['head_sha'][:10]} ({info['class']})", artifacts=[pr.get("url", "")],
                             data={"class": info["class"], "gh": result}))


def cmd_close(a) -> int:
    facts = issues.issue_facts(a.number)
    comment = Path(a.comment_file).read_text(encoding="utf-8")
    fails = issues.close_gates(facts, a.reason, comment, a.closed_this_run)
    if fails:
        return out.emit(out.refused("gate(s) failed: " + " | ".join(fails), data=facts))
    if a.dry_run:
        return out.emit(out.dry_run(f"would close #{a.number} as {a.reason}", data=facts))
    issues.perform_close(a.number, a.reason, comment)
    return out.emit(out.done(f"closed #{a.number} as {a.reason}", artifacts=[f"#{a.number}"], data=facts))


def cmd_floodgate(a) -> int:
    counts = issues.flood_counts(a.since)
    return out.emit(out.done(f"mode {counts['mode']}: {counts['new_prs']} new outside PR(s), {counts['new_issues']} new outside issue(s)", data=counts))


def cmd_heartbeat(a) -> int:
    line = issues.heartbeat_line(a.role, a.status, a.closes, a.reverts, a.holds)
    if a.dry_run:
        return out.emit(out.dry_run(line))
    issues.write_heartbeat(line)
    return out.emit(out.done(line))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="hb", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("doctor"); s.add_argument("--expect-login"); s.add_argument("--no-network", action="store_true"); s.set_defaults(fn=cmd_doctor)
    s = sub.add_parser("commands"); s.add_argument("--since"); s.set_defaults(fn=cmd_commands)
    s = sub.add_parser("state"); s.add_argument("action", choices=["read", "init", "update"]); s.add_argument("--patch"); s.add_argument("--patch-file")
    s.add_argument("--expect-updated-at"); s.add_argument("--open-prs", help="comma-separated PR numbers to keep in screened"); s.add_argument("--dry-run", action="store_true"); s.set_defaults(fn=cmd_state)
    s = sub.add_parser("classify-pr"); s.add_argument("number", type=int); s.set_defaults(fn=cmd_classify)
    s = sub.add_parser("screen-paths"); s.add_argument("number", type=int); s.set_defaults(fn=cmd_screen_paths)
    s = sub.add_parser("merge-pr"); s.add_argument("number", type=int); s.add_argument("--sha", required=True); s.add_argument("--dry-run", action="store_true"); s.set_defaults(fn=cmd_merge)
    s = sub.add_parser("close-issue"); s.add_argument("number", type=int); s.add_argument("--reason", required=True); s.add_argument("--comment-file", required=True)
    s.add_argument("--closed-this-run", type=int, default=0); s.add_argument("--dry-run", action="store_true"); s.set_defaults(fn=cmd_close)
    s = sub.add_parser("floodgate"); s.add_argument("--since"); s.set_defaults(fn=cmd_floodgate)
    s = sub.add_parser("heartbeat"); s.add_argument("--role", required=True, choices=config.ROLES); s.add_argument("--status", required=True, choices=["ok", "warning", "error", "paused"])
    s.add_argument("--closes", type=int, default=0); s.add_argument("--reverts", type=int, default=0); s.add_argument("--holds", type=int, default=0); s.add_argument("--dry-run", action="store_true"); s.set_defaults(fn=cmd_heartbeat)

    a = p.parse_args(argv)
    if a.command == "state" and a.action == "update" and not a.expect_updated_at:
        p.error("state update needs --expect-updated-at from the last read")
    try:
        return a.fn(a)
    except gh.GhError as exc:
        return out.fail(f"gh: {exc}")


if __name__ == "__main__":
    sys.exit(main())
