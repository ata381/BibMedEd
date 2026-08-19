from unittest.mock import AsyncMock, Mock

from app.adapters.base import SearchResponse


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

    get_adapter_mock.assert_called_once_with("pubmed")
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
    get_adapter_mock.assert_called_once_with("pubmed")
    adapter.search.assert_awaited_once_with("machine learning")
    adapter.close.assert_awaited_once()