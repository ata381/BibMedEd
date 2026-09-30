"""A fake gh runner: canned responses keyed by a prefix of the argument list."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hbtools import gh  # noqa: E402


class FakeGh:
    def __init__(self):
        self.routes: list[tuple[tuple[str, ...], object]] = []
        self.calls: list[list[str]] = []

    def on(self, *prefix: str, reply=None, rc: int = 0, stderr: str = ""):
        self.routes.append((prefix, (reply, rc, stderr)))
        return self

    def __call__(self, args, stdin):
        self.calls.append(list(args))
        for prefix, (reply, rc, stderr) in self.routes:
            if tuple(args[: len(prefix)]) == prefix:
                text = reply if isinstance(reply, str) else json.dumps(reply)
                return gh.Result(rc, text if rc == 0 else "", stderr)
        raise AssertionError(f"unexpected gh call: {' '.join(args)}")

    def called(self, *prefix: str) -> bool:
        return any(tuple(c[: len(prefix)]) == prefix for c in self.calls)


@pytest.fixture
def fake(monkeypatch):
    f = FakeGh()
    monkeypatch.setattr(gh, "RUNNER", f)
    return f


def pr_fixture(**over) -> dict:
    base = {
        "number": 104,
        "title": "feat: add bibtex export",
        "author": {"login": "someone"},
        "headRefName": "feature/bibtex",
        "headRefOid": "abcdef1234567890abcdef1234567890abcdef12",
        "headRepository": {"name": "BibMedEd"},
        "headRepositoryOwner": {"login": "ata381"},
        "isDraft": False,
        "createdAt": "2026-10-01T00:00:00Z",
        "body": "Closes #60",
        "baseRefName": "master",
        "mergeStateStatus": "CLEAN",
        "mergeable": "MERGEABLE",
        "statusCheckRollup": [
            {"name": "Backend tests (Python 3.12)", "conclusion": "SUCCESS"},
            {"name": "Backend tests (Python 3.13)", "conclusion": "SUCCESS"},
            {"name": "Frontend build", "conclusion": "SUCCESS"},
            {"name": "Docs build (MkDocs strict)", "conclusion": "SUCCESS"},
            {"name": "Docker build smoke test", "conclusion": "SUCCESS"},
            {"name": "E2E accessibility (Chromium)", "conclusion": "SUCCESS"},
        ],
        "files": [{"path": "bibmeded/bibmeded/services/export.py"}, {"path": "bibmeded/tests/test_export.py"}],
        "labels": [],
        "url": "https://github.com/ata381/BibMedEd/pull/104",
        "reviews": [],
        "commits": [],
    }
    base.update(over)
    return base


def review_fixture(*, codex_thread=False, resolved=True, unresolved=0, codex_review=False, commits=(), approved_by=None) -> dict:
    threads = []
    if codex_thread:
        threads.append({"isResolved": resolved, "resolvedBy": {"login": "ata381"},
                        "comments": {"nodes": [{"author": {"login": "chatgpt-codex-connector"}, "createdAt": "2026-10-01T01:00:00Z"}]}})
    for _ in range(unresolved):
        threads.append({"isResolved": False, "resolvedBy": None,
                        "comments": {"nodes": [{"author": {"login": "chatgpt-codex-connector"}, "createdAt": "2026-10-01T01:00:00Z"}]}})
    reviews = []
    if codex_review:
        reviews.append({"author": {"login": "chatgpt-codex-connector"}, "state": "COMMENTED", "submittedAt": "2026-10-01T01:00:00Z"})
    if approved_by:
        reviews.append({"author": {"login": approved_by}, "state": "APPROVED", "submittedAt": "2026-10-01T02:00:00Z"})
    return {
        "reviewThreads": {"nodes": threads},
        "reviews": {"nodes": reviews},
        "commits": {"nodes": [{"commit": {"committedDate": c}} for c in commits]},
    }
