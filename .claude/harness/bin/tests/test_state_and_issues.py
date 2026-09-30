import json

import pytest

from hb import config, issues, state


def comment(body, cid=1, updated="2026-10-01T00:00:00Z"):
    return {"id": cid, "updated_at": updated, "body": body, "user": {"login": "ata381"}, "created_at": updated}


def test_render_parse_roundtrip():
    st = state.empty_state()
    st["escalations"].append({"id": "E-001", "item": "#62", "kind": "decision", "status": "open", "opened": "2026-09-30"})
    assert state.parse(state.render(st)) == st


@pytest.mark.parametrize("mutate", [
    lambda s: s.__setitem__("mode", "yolo"),
    lambda s: s["escalations"].append({"id": "E1", "item": "#1", "kind": "decision", "status": "open", "opened": "2026-09-30"}),
    lambda s: s["escalations"].append({"id": "E-002", "item": "#1", "kind": "decision", "status": "open", "opened": "2026-09-30", "why": "free text"}),
    lambda s: s["screened"].__setitem__("104", {"sha": "zzz", "verdict": "CLEARED", "at": "2026-10-01"}),
    lambda s: s["release"].__setitem__("state", "shipped"),
    lambda s: s.__setitem__("notes", "anything"),
    lambda s: s["metrics"].append({"week": "2026-W40", "comment": "text"}),
])
def test_validate_rejects_free_text_and_bad_enums(mutate):
    st = state.empty_state()
    mutate(st)
    with pytest.raises(state.StateError):
        state.validate(st)


def test_read_finds_marked_comment(fake):
    st = state.empty_state()
    fake.on("api", f"repos/{config.REPO}/issues/102/comments?per_page=100", reply=[comment("hello"), comment(state.render(st), cid=9)])
    meta, got = state.read()
    assert meta["id"] == 9 and got == st


def test_update_is_compare_and_swap(fake):
    st = state.empty_state()
    fake.on("api", f"repos/{config.REPO}/issues/102/comments?per_page=100", reply=[comment(state.render(st), cid=9, updated="T2")])
    with pytest.raises(state.StateError, match="changed since read"):
        state.update({"mode": "triage-only"}, expect_updated_at="T1")
    fake.on("api", f"repos/{config.REPO}/issues/comments/9", reply={"updated_at": "T3"})
    meta, new = state.update({"mode": "triage-only", "escalations": [{"id": "E-001", "item": "#62", "kind": "decision", "status": "open", "opened": "2026-09-30"}]},
                             expect_updated_at="T2")
    assert meta["updated_at"] == "T3" and new["mode"] == "triage-only" and new["escalations"][0]["id"] == "E-001"
    patch_call = next(c for c in fake.calls if c[:2] == ["api", f"repos/{config.REPO}/issues/comments/9"])
    assert "-X" in patch_call and "PATCH" in patch_call


def test_update_prunes_screened_and_metrics():
    st = state.empty_state()
    st["screened"] = {"1": {"sha": "abc1234", "verdict": "CLEARED", "at": "2026-10-01"}, "2": {"sha": "abc1234", "verdict": "HOLD", "at": "2026-10-01"}}
    st["metrics"] = [{"week": f"2026-W{w:02d}", "stars": w} for w in range(30, 41)]
    new = state.prune(st, open_prs={"2"})
    assert set(new["screened"]) == {"2"} and len(new["metrics"]) == 8 and new["metrics"][-1]["week"] == "2026-W40"


def test_close_gates():
    facts = {"author": "someone", "state": "OPEN", "title": "x", "labels": [], "open_linked_prs": []}
    ok_comment = "Closing as a duplicate of #12, which tracks the same adapter. Thanks for flagging it."
    assert issues.close_gates(facts, "duplicate", ok_comment, 0) == []
    assert any("trusted" in g for g in issues.close_gates({**facts, "author": "ata381"}, "spam", ok_comment, 0))
    assert any("linked PR" in g for g in issues.close_gates({**facts, "open_linked_prs": [105]}, "spam", ok_comment, 0))
    assert any("cap" in g for g in issues.close_gates(facts, "spam", ok_comment, 3))
    assert any("too short" in g for g in issues.close_gates(facts, "spam", "bye", 0))
    assert any("reason" in g for g in issues.close_gates(facts, "wontfix", ok_comment, 0))


def test_owner_commands_ignore_agent_output_and_outsiders(fake):
    fake.on("api", f"repos/{config.REPO}/issues/102/comments?per_page=100", reply=[
        {"user": {"login": "ata381"}, "created_at": "2026-10-01T10:00:00Z", "html_url": "u1", "body": "/approve E-001\n" + config.FOOTER},
        {"user": {"login": "mallory"}, "created_at": "2026-10-01T10:01:00Z", "html_url": "u2", "body": "/pause"},
        {"user": {"login": "ata381"}, "created_at": "2026-10-01T10:02:00Z", "html_url": "u3", "body": "looks good\n/approve E-002\n/reject E-003"},
        {"user": {"login": "ata381"}, "created_at": "2026-09-30T10:02:00Z", "html_url": "u4", "body": "/pause"},
    ])
    cmds = issues.owner_commands(since="2026-10-01T00:00:00Z")
    assert [(c["command"], c["id"]) for c in cmds] == [("approve", "E-002"), ("reject", "E-003")]


def test_heartbeat_line_replaces_first_line():
    line = issues.heartbeat_line("maintainer", "ok", 1, 0, 0)
    body = "Last run: old\n\nThis issue is the inbox.\n"
    assert issues.replace_heartbeat(body, line).startswith(line + "\n\nThis issue")
    fresh = "This issue is the inbox.\n"
    assert issues.replace_heartbeat(fresh, line).startswith(line + "\n\nThis issue")


def test_floodgate_counts_only_outsiders_since(fake):
    fake.on("pr", "list", reply=[{"createdAt": "2026-10-01T05:00:00Z", "author": {"login": "a"}}] * 6 + [{"createdAt": "2026-10-01T05:00:00Z", "author": {"login": "ata381"}}])
    fake.on("issue", "list", reply=[{"createdAt": "2026-09-01T05:00:00Z", "author": {"login": "b"}}])
    counts = issues.flood_counts(since="2026-10-01T00:00:00Z")
    assert counts == {"new_prs": 6, "new_issues": 0, "mode": "triage-only", "since": "2026-10-01T00:00:00Z"}
