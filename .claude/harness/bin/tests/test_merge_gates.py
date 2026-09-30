from datetime import date, datetime, timezone

from conftest import pr_fixture, review_fixture
from hbtools import classify, merge, state

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)  # every fixture PR is 36 h old
SHA = "abcdef1234567890abcdef1234567890abcdef12"
OCTOBER = date(2026, 10, 5)
NOVEMBER = date(2026, 11, 5)


def gates(pr, review=None, st=None, today=OCTOBER):
    info = classify.classify(pr, NOW)
    return merge.evaluate(pr, info, review or review_fixture(codex_review=True), st or state.empty_state(), NOW, today)


def test_owner_pr_clean_merges():
    assert gates(pr_fixture(author={"login": "ata381"})) == []


def test_developer_pr_clean_merges():
    assert gates(pr_fixture(author={"login": "MugeBakiryol"})) == []


def test_draft_and_wip_refused():
    assert any("draft" in g for g in gates(pr_fixture(author={"login": "ata381"}, isDraft=True)))
    assert any("wip" in g for g in gates(pr_fixture(author={"login": "ata381"}, labels=[{"name": "WIP"}])))


def test_merge_state_must_be_clean():
    fails = gates(pr_fixture(author={"login": "ata381"}, mergeStateStatus="BEHIND"))
    assert any("mergeStateStatus" in g for g in fails)


def test_required_checks_and_frontend_e2e():
    pr = pr_fixture(author={"login": "ata381"})
    pr["statusCheckRollup"] = [c for c in pr["statusCheckRollup"] if c["name"] != "Docs build (MkDocs strict)"]
    assert any("Docs build" in g for g in gates(pr))
    fe = pr_fixture(author={"login": "ata381"}, files=[{"path": "bibmeded/frontend/src/app/page.tsx"}])
    fe["statusCheckRollup"] = [c for c in fe["statusCheckRollup"] if not c["name"].startswith("E2E")]
    assert any("E2E" in g for g in gates(fe))


def test_unresolved_thread_refused():
    fails = gates(pr_fixture(author={"login": "ata381"}), review_fixture(codex_review=True, unresolved=1))
    assert any("unresolved" in g for g in fails)


def test_codex_grace_for_humans():
    young = pr_fixture(author={"login": "ata381"}, createdAt="2026-10-02T11:00:00Z")
    assert any("no Codex review yet" in g for g in gates(young, review_fixture()))
    old = pr_fixture(author={"login": "ata381"}, createdAt="2026-10-01T00:00:00Z")
    assert gates(old, review_fixture()) == []


def agent_pr(**over):
    fields = {"author": {"login": "ata381"}, "headRefName": "claude/60-bibtex", "body": f"<!-- bibmeded-worker sha={SHA} -->"}
    fields.update(over)
    return pr_fixture(**fields)


def test_agent_pr_requires_codex_and_later_run():
    assert any("Codex review" in g for g in gates(agent_pr(), review_fixture()))
    young = agent_pr(createdAt="2026-10-02T11:00:00Z")
    assert any("later run" in g for g in gates(young, review_fixture(codex_review=True)))


def test_agent_pr_resolved_codex_thread_needs_fix_commit():
    no_fix = review_fixture(codex_thread=True, resolved=True, commits=("2026-10-01T00:30:00Z",))
    assert any("without a later fix commit" in g for g in gates(agent_pr(), no_fix))
    fixed = review_fixture(codex_thread=True, resolved=True, commits=("2026-10-01T00:30:00Z", "2026-10-01T02:00:00Z"))
    assert gates(agent_pr(), fixed) == []


def test_unverified_agent_branch_refused():
    pr = pr_fixture(author={"login": "ata381"}, headRefName="claude/wip", body="no marker")
    assert any("without a valid marker" in g for g in gates(pr))


def test_never_merge_paths_refused_for_everyone():
    for login in ("ata381", "MugeBakiryol"):
        pr = pr_fixture(author={"login": login}, files=[{"path": ".claude/harness/constitution.md"}])
        assert any("never-merge" in g for g in gates(pr))
    pr = pr_fixture(author={"login": "ata381"}, files=[{"path": "CONTRIBUTING.md"}])
    assert any("never-merge" in g for g in gates(pr))


def test_release_prep_exception_only_for_allowed_files():
    ok = agent_pr(headRefName="claude/release-v0.5.0", files=[{"path": "CITATION.cff"}, {"path": "CHANGELOG.md"}, {"path": "bibmeded/pyproject.toml"}])
    review = review_fixture(codex_review=True)
    assert gates(ok, review, today=NOVEMBER) == []
    bad = agent_pr(headRefName="claude/release-v0.5.0", files=[{"path": "CITATION.cff"}, {"path": ".github/workflows/release.yml"}])
    assert any("never-merge" in g for g in gates(bad, review, today=NOVEMBER))


def test_dependabot_cooldown_and_actions_bump():
    fresh = pr_fixture(author={"login": "dependabot[bot]"}, createdAt="2026-10-01T00:00:00Z", title="chore(deps): bump httpx")
    assert any("cooldown" in g for g in gates(fresh))
    aged = pr_fixture(author={"login": "dependabot[bot]"}, createdAt="2026-09-20T00:00:00Z", title="chore(ci): bump actions/checkout",
                      files=[{"path": ".github/workflows/ci.yml"}])
    assert gates(aged) == []
    mixed = pr_fixture(author={"login": "dependabot[bot]"}, createdAt="2026-09-20T00:00:00Z", title="chore(ci): bump x",
                       files=[{"path": ".github/workflows/ci.yml"}, {"path": ".github/CODEOWNERS"}])
    assert any("never-merge" in g for g in gates(mixed))


def test_external_needs_cleared_verdict_for_current_sha():
    pr = pr_fixture(author={"login": "newbie"}, headRepositoryOwner={"login": "newbie"})
    assert any("no recorded screen verdict" in g for g in gates(pr))
    st = state.empty_state()
    st["screened"]["104"] = {"sha": "0000000", "verdict": "CLEARED", "at": "2026-10-01"}
    assert any("re-screen" in g for g in gates(pr, st=st))
    st["screened"]["104"] = {"sha": SHA, "verdict": "HOLD", "at": "2026-10-01"}
    assert any("verdict is HOLD" in g for g in gates(pr, st=st))
    st["screened"]["104"] = {"sha": SHA, "verdict": "CLEARED-WITH-NOTES", "at": "2026-10-01"}
    assert gates(pr, st=st) == []


def test_needs_owner_title_and_dependency_manifests_refused_even_after_october():
    review = review_fixture(codex_review=True)
    titled = agent_pr(title="needs-owner: date parsing needs a new package")
    assert any("needs-owner" in g for g in gates(titled, review, today=NOVEMBER))
    manifest = agent_pr(files=[{"path": "bibmeded/pyproject.toml"}, {"path": "bibmeded/tests/test_dates.py"}])
    assert any("dependency manifest" in g for g in gates(manifest, review, today=NOVEMBER))
    owner_manifest = pr_fixture(author={"login": "ata381"}, files=[{"path": "bibmeded/frontend/package.json"}])
    assert any("dependency manifest" in g for g in gates(owner_manifest, review))
    dependabot = pr_fixture(author={"login": "dependabot[bot]"}, createdAt="2026-09-20T00:00:00Z", title="chore(deps): bump httpx",
                            files=[{"path": "bibmeded/pyproject.toml"}])
    assert gates(dependabot, review) == []


def test_worker_allowlist_until_end_of_october():
    pr = agent_pr(files=[{"path": "bibmeded/bibmeded/routers/search.py"}])
    review = review_fixture(codex_review=True)
    assert any("sprint allowlist" in g for g in gates(pr, review, today=OCTOBER))
    assert gates(pr, review_fixture(codex_review=True, approved_by="MugeBakiryol"), today=OCTOBER) == []
    assert gates(pr, review, today=NOVEMBER) == []
