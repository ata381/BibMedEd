import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.adapters.base import RawRecord, SearchResponse
from app.adapters.semantic_scholar import SemanticScholarAdapter


@pytest.fixture
def adapter():
    return SemanticScholarAdapter()


# Realistic Semantic Scholar Graph API v1 shapes —
# see https://api.semanticscholar.org/api-docs/graph

SEARCH_PAGE1 = {
    "total": 3,
    "offset": 0,
    "next": 2,
    "data": [
        {"paperId": "s2id-1", "externalIds": {"DOI": "10.1001/jama.2024.0001"}, "title": "AI in Medical Education"},
        {"paperId": "s2id-2", "externalIds": {"DOI": "10.1136/bmj.n71"}, "title": "PRISMA 2020"},
    ],
}

SEARCH_PAGE2 = {
    "total": 3,
    "offset": 2,
    # No "next" key — pagination terminates.
    "data": [
        {"paperId": "s2id-3", "externalIds": {"DOI": "10.1007/s12345-024-67890-1"}, "title": "A third paper"},
    ],
}

PAPER_BATCH = [
    {
        "paperId": "s2id-1",
        "externalIds": {"DOI": "10.1001/JAMA.2024.0001", "PubMed": "38765432"},
        "title": "Artificial Intelligence in Undergraduate Medical Curricula",
        "abstract": "This study reviews...",
        "year": 2024,
        "publicationTypes": ["JournalArticle"],
        "journal": {"name": "JAMA", "volume": "331"},
        "publicationVenue": {"name": "JAMA", "issn": "0098-7484"},
        "fieldsOfStudy": ["Medicine", "Computer Science"],
        "authors": [
            {
                "name": "Jane Doe",
                "externalIds": {"ORCID": "https://orcid.org/0000-0001-2345-6789"},
            },
            {"name": "John Smith"},
        ],
        "references": [
            {"externalIds": {"DOI": "10.1056/NEJMra2107479"}},
            {"externalIds": {"DOI": "10.1136/BMJ.N71"}},  # uppercase → must lowercase
            {"externalIds": {"ArXiv": "2305.12345"}},  # no DOI → dropped
        ],
    },
    None,  # batch endpoint returns None for ids that couldn't be resolved
]


def _mock_resp(payload):
    resp = AsyncMock()
    resp.json.return_value = payload
    resp.raise_for_status = lambda: None
    return resp


def test_metadata():
    a = SemanticScholarAdapter()
    assert a.name == "semanticscholar"
    assert a.display_name == "Semantic Scholar"
    assert a.requires_api_key is False


def test_methodology_label():
    a = SemanticScholarAdapter()
    assert a.methodology_label() == "Semantic Scholar Graph API"


def test_api_key_sets_header():
    a = SemanticScholarAdapter(api_key="abc-123")
    assert a._client.headers.get("x-api-key") == "abc-123"


def test_search_returns_paperids(adapter):
    with patch.object(adapter._client, "get", return_value=_mock_resp(SEARCH_PAGE1)):
        result = asyncio.run(adapter.search("medical education AI"))
    assert isinstance(result, SearchResponse)
    assert result.total_count == 3
    assert result.ids == ["s2id-1", "s2id-2"]


def test_search_applies_year_filter(adapter):
    captured: dict = {}

    async def capturing_get(url, params=None):
        captured["params"] = params
        return _mock_resp(SEARCH_PAGE1)

    with patch.object(adapter._client, "get", side_effect=capturing_get):
        asyncio.run(adapter.search("x", year_start=2020, year_end=2024))
    assert captured["params"]["year"] == "2020-2024"


def test_search_paginated_walks_offset(adapter):
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
    assert batches == [["s2id-1", "s2id-2"], ["s2id-3"]]


def test_search_paginated_stops_at_offset_cap(adapter):
    """Upstream offset cap is 9999 inclusive. `next=10000` exceeds the cap;
    pagination must terminate without making a follow-up request."""

    async def mock_get(url, params=None):
        return _mock_resp({
            "total": 50000,
            "offset": params.get("offset", 0) if params else 0,
            "next": 10000,
            "data": [{"paperId": f"id-{params.get('offset', 0)}"}],
        })

    with patch.object(adapter._client, "get", side_effect=mock_get):
        batches: list[list[str]] = []

        async def run():
            async for batch in adapter.search_paginated("x"):
                batches.append(batch)

        asyncio.run(run())
    # One yield (offset=0), then stop because next=10000 > cap.
    assert len(batches) == 1


def test_search_paginated_fetches_the_last_valid_offset(adapter):
    """next=9999 is a valid offset (cap is inclusive). The loop must fetch it
    before terminating — regression guard against an off-by-one that would
    silently drop the last page of any maxed-out search."""
    call_count = 0

    async def mock_get(url, params=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _mock_resp({"total": 50000, "offset": 0, "next": 9999, "data": [{"paperId": "id-0"}]})
        return _mock_resp({"total": 50000, "offset": 9999, "data": [{"paperId": "id-9999"}]})

    with patch.object(adapter._client, "get", side_effect=mock_get):
        batches: list[list[str]] = []

        async def run():
            async for batch in adapter.search_paginated("x"):
                batches.append(batch)

        asyncio.run(run())
    assert batches == [["id-0"], ["id-9999"]]


def test_search_paginated_applies_year_filter(adapter):
    captured: list[dict] = []

    async def capturing_get(url, params=None):
        captured.append(dict(params or {}))
        return _mock_resp(SEARCH_PAGE2)  # no `next` → single batch then stop

    with patch.object(adapter._client, "get", side_effect=capturing_get):
        async def run():
            async for _ in adapter.search_paginated("x", year_start=2020, year_end=2024):
                pass
        asyncio.run(run())
    assert captured[0]["year"] == "2020-2024"


def test_fetch_chunks_large_id_lists(adapter):
    """500+ IDs must be split into chunks so /paper/batch never returns 400."""
    post_calls: list[dict] = []

    async def capturing_post(url, params=None, json=None):
        post_calls.append({"params": params, "ids_len": len(json["ids"])})
        # Return one record per id so we can verify both chunks were fetched.
        return _mock_resp([{
            "paperId": f"id-{i}",
            "externalIds": {"DOI": f"10.0/{i}"},
            "title": f"P{i}",
            "authors": [],
            "year": 2024,
        } for i in range(len(json["ids"]))])

    big_ids = [f"id-{i}" for i in range(750)]
    with patch.object(adapter._client, "post", side_effect=capturing_post):
        records = asyncio.run(adapter.fetch(big_ids))
    assert [c["ids_len"] for c in post_calls] == [500, 250]
    assert len(records) == 750


def test_fetch_maps_to_rawrecord(adapter):
    with patch.object(adapter._client, "post", return_value=_mock_resp(PAPER_BATCH)):
        records = asyncio.run(adapter.fetch(["s2id-1", "s2id-missing"]))
    assert len(records) == 1  # the None entry is dropped
    r = records[0]
    assert isinstance(r, RawRecord)
    assert r.source_database == "semanticscholar"
    assert r.source_id == "s2id-1"
    assert r.title == "Artificial Intelligence in Undergraduate Medical Curricula"
    assert r.year == 2024
    assert r.journal_name == "JAMA"
    assert r.journal_issn == "0098-7484"
    assert r.publication_type == "JournalArticle"
    # DOI must be lowercased to be dedup-compatible with PubMed/OpenAlex/CrossRef.
    assert r.doi == "10.1001/jama.2024.0001"
    assert r.external_ids["doi"] == "10.1001/jama.2024.0001"
    assert r.external_ids["pmid"] == "38765432"
    assert r.external_ids["semantic_scholar"] == "s2id-1"
    assert [a.name for a in r.authors] == ["Jane Doe", "John Smith"]
    assert r.authors[0].orcid == "0000-0001-2345-6789"
    assert r.keywords == ["Medicine", "Computer Science"]
    # References — DOIs lowercased, ArXiv-only ref dropped.
    assert r.references == ["10.1056/nejmra2107479", "10.1136/bmj.n71"]
    # Non-PubMed adapters always emit explicit empty mesh_terms.
    assert r.mesh_terms == []


def test_fetch_handles_empty_ids(adapter):
    records = asyncio.run(adapter.fetch([]))
    assert records == []


def test_fetch_returns_empty_on_non_list_response(adapter):
    """If the API returns an error shape (dict with `error` key), don't crash."""
    with patch.object(adapter._client, "post", return_value=_mock_resp({"error": "rate limit"})):
        records = asyncio.run(adapter.fetch(["s2id-1"]))
    assert records == []


def test_doi_normalisation_for_dedup_compatibility(adapter):
    """The cross-source dedup service keys on external_ids['doi'] lowercased.
    Verify the adapter emits lowercase DOIs so dedup matches the other three sources."""
    payload = [{
        "paperId": "s2id-x",
        "externalIds": {"DOI": "10.1001/JAMA.2024.0001"},
        "title": "Upper DOI",
        "authors": [],
        "year": 2024,
    }]
    with patch.object(adapter._client, "post", return_value=_mock_resp(payload)):
        records = asyncio.run(adapter.fetch(["s2id-x"]))
    assert records[0].external_ids["doi"] == "10.1001/jama.2024.0001"
    assert records[0].doi == "10.1001/jama.2024.0001"


def test_close_releases_http_client(adapter):
    async def run():
        await adapter.close()
    asyncio.run(run())
    # Subsequent close should be idempotent (httpx allows it).
    asyncio.run(run())
