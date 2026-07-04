import asyncio
import logging
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.adapters.crossref import CrossrefAdapter
from app.adapters.base import RawRecord, SearchResponse


@pytest.fixture
def adapter():
    return CrossrefAdapter()


# Realistic CrossRef payloads — shapes match what api.crossref.org actually returns.

SEARCH_PAGE1 = {
    "status": "ok",
    "message": {
        "total-results": 3,
        "items-per-page": 2,
        "next-cursor": "AoJ50bP1n+gCPxhodHRwOi8vZHguZG9pLm9yZy8xMC4xMDA3L3MwMDIxMy0wMTctNDk1Ny01",
        "items": [
            {"DOI": "10.1001/jama.2024.0001", "title": ["AI in Medical Education"]},
            {"DOI": "10.1136/bmj.n71", "title": ["PRISMA 2020"]},
        ],
    },
}

SEARCH_PAGE2 = {
    "status": "ok",
    "message": {
        "total-results": 3,
        "items-per-page": 2,
        "next-cursor": None,
        "items": [
            {"DOI": "10.1007/s12345-024-67890-1", "title": ["A third paper"]},
        ],
    },
}

WORK_DETAIL = {
    "status": "ok",
    "message": {
        "DOI": "10.1001/jama.2024.0001",
        "title": ["Artificial Intelligence in Undergraduate Medical Curricula"],
        "container-title": ["JAMA"],
        "ISSN": ["0098-7484"],
        "type": "journal-article",
        "published-print": {"date-parts": [[2024, 5, 14]]},
        "abstract": "<jats:p>This study reviews...</jats:p>",
        "subject": ["Medical Education", "Artificial Intelligence"],
        "author": [
            {
                "given": "Jane",
                "family": "Doe",
                "ORCID": "https://orcid.org/0000-0001-2345-6789",
                "affiliation": [{"name": "Harvard Medical School"}],
            },
            {
                "given": "John",
                "family": "Smith",
                "affiliation": [],
            },
        ],
        "reference": [
            {"DOI": "10.1056/NEJMra2107479"},
            {"DOI": "10.1136/BMJ.N71"},  # uppercase — should be normalised
            {"unstructured": "Some unstructured reference without DOI"},
        ],
    },
}

WORK_DETAIL_MINIMAL_YEAR_FALLBACK = {
    "status": "ok",
    "message": {
        "DOI": "10.0/sparse",
        "title": ["Sparse record"],
        "type": "journal-article",
        # No published-print; should fall back to published-online.
        "published-online": {"date-parts": [[2021]]},
        "container-title": [],
        "author": [],
    },
}


def _mock_resp(payload):
    resp = AsyncMock()
    resp.json.return_value = payload
    resp.raise_for_status = lambda: None
    return resp


def test_crossref_metadata():
    a = CrossrefAdapter()
    assert a.name == "crossref"
    assert a.display_name == "CrossRef"
    assert a.requires_api_key is False


def test_crossref_methodology_label():
    a = CrossrefAdapter()
    assert a.methodology_label() == "CrossRef API"


def test_crossref_search(adapter):
    with patch.object(adapter._client, "get", return_value=_mock_resp(SEARCH_PAGE1)):
        result = asyncio.run(adapter.search("medical education AI"))
    assert isinstance(result, SearchResponse)
    assert result.total_count == 3
    assert result.ids == ["10.1001/jama.2024.0001", "10.1136/bmj.n71"]


def test_crossref_search_includes_mailto_when_email_set():
    a = CrossrefAdapter(email="user@example.com")
    captured: dict = {}

    async def capturing_get(url, params=None):
        captured["url"] = url
        captured["params"] = params
        return _mock_resp(SEARCH_PAGE1)

    with patch.object(a._client, "get", side_effect=capturing_get):
        asyncio.run(a.search("x"))
    assert captured["params"]["mailto"] == "user@example.com"


def test_crossref_search_applies_year_filter(adapter):
    captured: dict = {}

    async def capturing_get(url, params=None):
        captured["params"] = params
        return _mock_resp(SEARCH_PAGE1)

    with patch.object(adapter._client, "get", side_effect=capturing_get):
        asyncio.run(adapter.search("x", year_start=2020, year_end=2024))
    assert captured["params"]["filter"] == "from-pub-date:2020-01-01,until-pub-date:2024-12-31"


def test_crossref_search_paginated_walks_cursor(adapter):
    call_count = 0

    async def mock_get(url, params=None):
        nonlocal call_count
        call_count += 1
        return _mock_resp(SEARCH_PAGE1 if call_count == 1 else SEARCH_PAGE2)

    with patch.object(adapter._client, "get", side_effect=mock_get):
        batches: list[list[str]] = []

        async def run():
            async for batch in adapter.search_paginated("test"):
                batches.append(batch)

        asyncio.run(run())
    assert len(batches) == 2
    assert batches[0] == ["10.1001/jama.2024.0001", "10.1136/bmj.n71"]
    assert batches[1] == ["10.1007/s12345-024-67890-1"]


def test_crossref_fetch_maps_to_rawrecord(adapter):
    with patch.object(adapter._client, "get", return_value=_mock_resp(WORK_DETAIL)):
        records = asyncio.run(adapter.fetch(["10.1001/jama.2024.0001"]))
    assert len(records) == 1
    r = records[0]
    assert isinstance(r, RawRecord)
    assert r.source_database == "crossref"
    assert r.source_id == "10.1001/jama.2024.0001"
    assert r.title == "Artificial Intelligence in Undergraduate Medical Curricula"
    assert r.year == 2024
    assert r.journal_name == "JAMA"
    assert r.journal_issn == "0098-7484"
    assert r.publication_type == "journal-article"
    assert r.doi == "10.1001/jama.2024.0001"
    assert r.external_ids["doi"] == "10.1001/jama.2024.0001"
    # Author parsing — given+family composed, ORCID URL stripped
    assert [a.name for a in r.authors] == ["Jane Doe", "John Smith"]
    assert r.authors[0].orcid == "0000-0001-2345-6789"
    assert r.authors[0].affiliation == "Harvard Medical School"
    assert r.authors[1].affiliation is None
    assert r.keywords == ["Medical Education", "Artificial Intelligence"]
    # References — both DOIs lower-cased, unstructured ref dropped
    assert r.references == ["10.1056/nejmra2107479", "10.1136/bmj.n71"]
    assert r.abstract == "<jats:p>This study reviews...</jats:p>"


def test_crossref_fetch_year_falls_back_to_published_online(adapter):
    with patch.object(
        adapter._client,
        "get",
        return_value=_mock_resp(WORK_DETAIL_MINIMAL_YEAR_FALLBACK),
    ):
        records = asyncio.run(adapter.fetch(["10.0/sparse"]))
    assert records[0].year == 2021


def test_crossref_fetch_skips_records_on_http_error(adapter):
    async def mock_get(url, params=None):
        raise httpx.HTTPError("network error")

    with patch.object(adapter._client, "get", side_effect=mock_get):
        records = asyncio.run(adapter.fetch(["10.0/never-found"]))
    assert records == []


def test_crossref_fetch_logs_warning_on_swallowed_http_error(adapter, caplog):
    async def mock_get(url, params=None):
        raise httpx.HTTPError("network error")

    with caplog.at_level(logging.WARNING):
        with patch.object(adapter._client, "get", side_effect=mock_get):
            records = asyncio.run(adapter.fetch(["10.0/never-found"]))

    assert records == []
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING
    assert "10.0/never-found" in caplog.text


def test_crossref_fetch_logs_status_code_on_http_status_error(adapter, caplog):
    request = httpx.Request("GET", f"https://api.crossref.org/works/10.0/broken")
    response = httpx.Response(status_code=503, request=request)
    error = httpx.HTTPStatusError("server error", request=request, response=response)

    async def mock_get(url, params=None):
        raise error

    with caplog.at_level(logging.WARNING):
        with patch.object(adapter._client, "get", side_effect=mock_get):
            records = asyncio.run(adapter.fetch(["10.0/broken"]))

    assert records == []
    assert "503" in caplog.text
    assert "10.0/broken" in caplog.text


def test_crossref_fetch_raises_after_consecutive_failure_threshold(adapter):
    """A systemic CrossRef outage (every DOI failing) must surface as an
    exception rather than silently returning an empty result set."""

    async def mock_get(url, params=None):
        raise httpx.HTTPError("network error")

    dois = [f"10.0/outage-{i}" for i in range(10)]
    with patch.object(adapter._client, "get", side_effect=mock_get):
        with pytest.raises(RuntimeError, match="consecutive"):
            asyncio.run(adapter.fetch(dois))


def test_crossref_fetch_does_not_raise_when_failures_are_not_consecutive(adapter):
    """9 failures, one success, then 9 more failures — never hits the
    10-in-a-row threshold, so this must NOT raise."""
    call_count = 0

    async def mock_get(url, params=None):
        nonlocal call_count
        call_count += 1
        if call_count == 10:
            return _mock_resp(WORK_DETAIL)
        raise httpx.HTTPError("network error")

    dois = [f"10.0/mixed-{i}" for i in range(19)]
    with patch.object(adapter._client, "get", side_effect=mock_get):
        records = asyncio.run(adapter.fetch(dois))
    assert len(records) == 1


def test_crossref_fetch_below_threshold_does_not_raise(adapter):
    async def mock_get(url, params=None):
        raise httpx.HTTPError("network error")

    dois = [f"10.0/partial-{i}" for i in range(9)]
    with patch.object(adapter._client, "get", side_effect=mock_get):
        records = asyncio.run(adapter.fetch(dois))
    assert records == []


def test_crossref_doi_normalisation_for_dedup_compatibility(adapter):
    """The cross-source dedup service keys on external_ids['doi'] lowercased.
    Verify CrossRefAdapter emits lowercase DOIs so dedup matches OpenAlex /
    PubMed records seamlessly."""
    upper_doi_payload = {
        "status": "ok",
        "message": {
            "DOI": "10.1001/JAMA.2024.0001",
            "title": ["Upper DOI"],
            "type": "journal-article",
            "container-title": [],
            "author": [],
            "published-print": {"date-parts": [[2024]]},
        },
    }
    with patch.object(adapter._client, "get", return_value=_mock_resp(upper_doi_payload)):
        records = asyncio.run(adapter.fetch(["10.1001/JAMA.2024.0001"]))
    assert records[0].external_ids["doi"] == "10.1001/jama.2024.0001"
    assert records[0].doi == "10.1001/jama.2024.0001"
