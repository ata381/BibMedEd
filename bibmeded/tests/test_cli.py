import json
from unittest.mock import AsyncMock, Mock
from types import SimpleNamespace

import httpx
import pytest
from lxml import etree

from app.adapters.base import SearchResponse
from app.config import settings


def test_search_dry_run_prints_estimated_count(monkeypatch, capsys):
    from app import cli

    adapter = AsyncMock()
    adapter.search.return_value = SearchResponse(
        total_count=1234,
        ids=["1", "2"],
    )

    get_adapter_mock = Mock(return_value=adapter)
    monkeypatch.setattr(cli, "get_adapter", get_adapter_mock)

    exit_code = cli.main(
        [
            "search",
            "machine learning",
            "--source",
            "pubmed",
            "--dry-run",
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "1234" in output

    get_adapter_mock.assert_called_once_with("pubmed", api_key="", rate_limit=3.0)
    adapter.search.assert_awaited_once_with("machine learning")
    adapter.fetch.assert_not_called()
    adapter.fetch_stream.assert_not_called()
    adapter.close.assert_awaited_once()


def test_search_dry_run_uses_pubmed_by_default(monkeypatch, capsys):
    from app import cli

    adapter = AsyncMock()
    adapter.search.return_value = SearchResponse(
        total_count=42,
        ids=[],
    )

    get_adapter_mock = Mock(return_value=adapter)
    monkeypatch.setattr(cli, "get_adapter", get_adapter_mock)

    exit_code = cli.main(
        [
            "search",
            "machine learning",
            "--dry-run",
        ]
    )

    capsys.readouterr()

    assert exit_code == 0
    get_adapter_mock.assert_called_once_with("pubmed", api_key="", rate_limit=3.0)
    adapter.search.assert_awaited_once_with("machine learning")
    adapter.close.assert_awaited_once()


def test_search_dry_run_wires_lens_api_key(monkeypatch, capsys):
    from app import cli

    test_value = "lens-" + "test-token"
    adapter = AsyncMock()
    adapter.search.return_value = SearchResponse(total_count=7, ids=[])
    get_adapter_mock = Mock(return_value=adapter)
    monkeypatch.setattr(cli, "get_adapter", get_adapter_mock)
    monkeypatch.setattr(settings, "lens_api_key", test_value)
    monkeypatch.setattr(cli, "adapter_kwargs", Mock(return_value={"api_key": test_value}), raising=False)

    exit_code = cli.main(["search", "medical education", "--source", "lens", "--dry-run"])

    assert exit_code == 0
    get_adapter_mock.assert_called_once_with("lens", api_key=test_value)
    assert "7" in capsys.readouterr().out


def test_search_dry_run_reports_missing_lens_key_without_api_call(monkeypatch, capsys):
    from app import cli

    monkeypatch.setattr(settings, "lens_api_key", "")
    get_adapter_mock = Mock()
    monkeypatch.setattr(cli, "get_adapter", get_adapter_mock)

    exit_code = cli.main(["search", "medical education", "--source", "lens", "--dry-run"])

    assert exit_code == 1
    assert "BIBMEDED_LENS_API_KEY" in capsys.readouterr().err
    get_adapter_mock.assert_not_called()


@pytest.mark.parametrize(
    ("source", "expected_kwargs"),
    [
        ("pubmed", {"api_key": "pm-key", "rate_limit": 9.5}),
        ("openalex", {"email": "openalex@example.org"}),
        ("crossref", {"email": "crossref@example.org"}),
        ("semanticscholar", {"api_key": "s2-key"}),
        ("lens", {"api_key": "lens-key"}),
    ],
)
def test_search_dry_run_uses_configured_kwargs_for_every_source(
    monkeypatch,
    capsys,
    source,
    expected_kwargs,
):
    from app import cli

    configured_values = {
        "pubmed_api_key": "pm-key",
        "pubmed_rate_limit": 9.5,
        "openalex_email": "openalex@example.org",
        "crossref_email": "crossref@example.org",
        "semantic_scholar_api_key": "s2-key",
        "lens_api_key": "lens-key",
    }
    for name, value in configured_values.items():
        monkeypatch.setattr(settings, name, value)

    adapter = AsyncMock()
    adapter.search.return_value = SearchResponse(total_count=1, ids=[])
    get_adapter_mock = Mock(return_value=adapter)
    monkeypatch.setattr(cli, "get_adapter", get_adapter_mock)

    exit_code = cli.main(["search", "medical education", "--source", source, "--dry-run"])

    assert exit_code == 0
    get_adapter_mock.assert_called_once_with(source, **expected_kwargs)
    capsys.readouterr()


def test_search_dry_run_reports_unknown_source_without_traceback(monkeypatch, capsys):
    from app import cli

    error = "Unknown adapter: unknown. Available: ['pubmed']"
    monkeypatch.setattr(cli, "get_adapter", Mock(side_effect=ValueError(error)))

    exit_code = cli.main(
        [
            "search",
            "machine learning",
            "--source",
            "unknown",
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == f"{error}\n"
    assert "Traceback" not in captured.err


def test_search_dry_run_reports_network_failure_without_traceback(monkeypatch, capsys):
    from app import cli

    adapter = AsyncMock()
    adapter.search.side_effect = httpx.ConnectError("connection failed")
    monkeypatch.setattr(cli, "get_adapter", Mock(return_value=adapter))

    exit_code = cli.main(
        [
            "search",
            "machine learning",
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == "Search failed: connection failed\n"
    assert "Traceback" not in captured.err
    adapter.close.assert_awaited_once()


@pytest.mark.parametrize(
    "parse_error",
    [
        json.JSONDecodeError("malformed JSON", "{", 0),
        etree.XMLSyntaxError("malformed XML", 1, 1, 1),
        ValueError("malformed adapter response"),
    ],
)
def test_search_dry_run_reports_response_parse_failure_without_traceback(
    monkeypatch,
    capsys,
    parse_error,
):
    from app import cli

    adapter = AsyncMock()
    adapter.search.side_effect = parse_error
    monkeypatch.setattr(cli, "get_adapter", Mock(return_value=adapter))

    exit_code = cli.main(
        [
            "search",
            "machine learning",
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == f"Search failed: {parse_error}\n"
    assert "Traceback" not in captured.err
    adapter.close.assert_awaited_once()


def test_search_dispatches_full_pipeline_and_reports_completion(monkeypatch, capsys):
    from app import cli

    project = SimpleNamespace(id=None)
    search_query = SimpleNamespace(
        id=None,
        status=cli.QueryStatus.pending,
        result_count=None,
    )

    class FakeDB:
        def __init__(self):
            self.refresh_count = 0
            self.closed = False

        def add(self, obj):
            pass

        def commit(self):
            pass

        def refresh(self, obj):
            if obj is project:
                project.id = 10
                return

            if obj is search_query:
                self.refresh_count += 1

                if search_query.id is None:
                    search_query.id = 20
                elif self.refresh_count >= 3:
                    search_query.status = cli.QueryStatus.completed
                    search_query.result_count = 99
                else:
                    search_query.status = cli.QueryStatus.running

        def close(self):
            self.closed = True

    db = FakeDB()

    monkeypatch.setattr(cli, "SessionLocal", Mock(return_value=db))
    monkeypatch.setattr(cli, "SearchProject", Mock(return_value=project))
    monkeypatch.setattr(cli, "SearchQuery", Mock(return_value=search_query))
    monkeypatch.setattr(cli.run_search, "delay", Mock())
    monkeypatch.setattr(cli.time, "sleep", Mock())

    exit_code = cli.main(
        [
            "search",
            "AI in medical education",
            "--source",
            "pubmed",
            "--year-start",
            "2020",
            "--year-end",
            "2025",
            "--max-results",
            "100",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "Completed: 99 records\n"
    assert "Search started (query_id=20)" in captured.err
    assert "Waiting for completion..." in captured.err

    cli.run_search.delay.assert_called_once_with(
        20,
        "pubmed",
        "2020",
        "2025",
        100,
    )

    assert db.closed is True


def test_search_returns_error_when_worker_marks_query_failed(monkeypatch, capsys):
    from app import cli

    project = SimpleNamespace(id=None)
    search_query = SimpleNamespace(
        id=None,
        status=cli.QueryStatus.pending,
        result_count=None,
    )

    class FakeDB:
        def __init__(self):
            self.refresh_count = 0
            self.closed = False

        def add(self, obj):
            pass

        def commit(self):
            pass

        def refresh(self, obj):
            if obj is project:
                project.id = 10
                return

            if obj is search_query:
                self.refresh_count += 1

                if search_query.id is None:
                    search_query.id = 20
                else:
                    search_query.status = cli.QueryStatus.failed

        def close(self):
            self.closed = True

    db = FakeDB()

    monkeypatch.setattr(cli, "SessionLocal", Mock(return_value=db))
    monkeypatch.setattr(cli, "SearchProject", Mock(return_value=project))
    monkeypatch.setattr(cli, "SearchQuery", Mock(return_value=search_query))
    monkeypatch.setattr(cli.run_search, "delay", Mock())
    monkeypatch.setattr(cli.time, "sleep", Mock())

    exit_code = cli.main(
        [
            "search",
            "AI in medical education",
            "--source",
            "pubmed",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Search failed" in captured.err
    assert db.closed is True

def test_full_search_invalid_source_fails_fast(monkeypatch, capsys):
    from app import cli

    monkeypatch.setattr(
        cli,
        "get_adapter",
        Mock(side_effect=ValueError("Unknown adapter: invalid")),
    )

    exit_code = cli.main(
        [
            "search",
            "AI in medical education",
            "--source",
            "invalid",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Unknown adapter: invalid" in captured.err
