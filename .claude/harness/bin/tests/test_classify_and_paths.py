from datetime import datetime, timezone

from conftest import pr_fixture
from hb import classify, config, paths

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def test_owner_pr_is_owner():
    info = classify.classify(pr_fixture(author={"login": "ata381"}), NOW)
    assert info["class"] == "owner"


def test_developer_pr_is_developer():
    info = classify.classify(pr_fixture(author={"login": "MugeBakiryol"}), NOW)
    assert info["class"] == "developer"


def test_fork_pr_is_external_even_with_trusted_login():
    info = classify.classify(pr_fixture(author={"login": "ata381"}, headRepositoryOwner={"login": "attacker"}), NOW)
    assert info["class"] == "external"


def test_dependabot_only_from_same_repo():
    assert classify.classify(pr_fixture(author={"login": "dependabot[bot]"}), NOW)["class"] == "dependabot"
    forked = pr_fixture(author={"login": "dependabot[bot]"}, headRepositoryOwner={"login": "x"})
    assert classify.classify(forked, NOW)["class"] == "external"


def test_agent_pr_needs_marker_with_matching_sha():
    sha = "abcdef1234567890abcdef1234567890abcdef12"
    good = pr_fixture(author={"login": "ata381"}, headRefName="claude/60-bibtex", body=f"x\n<!-- bibmeded-worker sha={sha[:12]} -->")
    assert classify.classify(good, NOW)["class"] == "agent"
    stale = pr_fixture(author={"login": "ata381"}, headRefName="claude/60-bibtex", body="<!-- bibmeded-worker sha=0000000 -->")
    assert classify.classify(stale, NOW)["class"] == "agent-unverified"
    none = pr_fixture(author={"login": "ata381"}, headRefName="claude/wip", body="work in progress")
    assert classify.classify(none, NOW)["class"] == "agent-unverified"


def test_marker_in_fork_pr_does_not_make_it_agent():
    sha = "abcdef1234567890abcdef1234567890abcdef12"
    pr = pr_fixture(author={"login": "mallory"}, headRepositoryOwner={"login": "mallory"}, headRefName="claude/57-fix",
                    body=f"<!-- bibmeded-worker sha={sha} -->")
    assert classify.classify(pr, NOW)["class"] == "external"


def test_age_hours():
    info = classify.classify(pr_fixture(createdAt="2026-10-01T09:30:00Z"), NOW)
    assert info["age_hours"] == 2.5


def test_glob_double_star_semantics():
    assert paths.matches(".github/workflows/ci.yml", ".github/**")
    assert paths.matches("bibmeded/frontend/CLAUDE.md", "**/CLAUDE.md")
    assert paths.matches("CLAUDE.md", "**/CLAUDE.md")
    assert not paths.matches("docs/CLAUDE.md.bak", "**/CLAUDE.md")
    assert paths.matches("bibmeded/alembic/versions/0004_x.py", "bibmeded/alembic/**")
    assert not paths.matches("bibmeded/bibmeded/alembic_helpers.py", "bibmeded/alembic/**")
    assert paths.matches("bibmeded/frontend/next.config.ts", "bibmeded/frontend/next.config.*")


def test_critical_list_catches_instruction_and_execution_surfaces():
    files = ["CONTRIBUTING.md", "bibmeded/bibmeded/adapters/CLAUDE.md", ".mcp.json", "mkdocs.yml",
             "bibmeded/frontend/package-lock.json", "bibmeded/alembic.ini", "docs/javascripts/x.js", "bibmeded/pyproject.toml"]
    hit = {p for p, _ in paths.hits(files, config.CRITICAL_PATHS)}
    assert hit == set(files)
    assert paths.hits(["bibmeded/bibmeded/adapters/doaj.py", "docs/adapters.md"], config.CRITICAL_PATHS) == []


def test_worker_allowlist():
    assert paths.all_within(["bibmeded/tests/test_x.py", "docs/how-to-cite.md"], config.WORKER_ALLOWLIST) == []
    assert paths.all_within(["bibmeded/bibmeded/routers/search.py"], config.WORKER_ALLOWLIST) == ["bibmeded/bibmeded/routers/search.py"]
