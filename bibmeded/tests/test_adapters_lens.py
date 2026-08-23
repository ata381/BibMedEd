import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.adapters.base import RawRecord, SearchResponse
from app.adapters import lens as lens_module
from app.adapters.lens import LensAdapter


SEARCH_PAGE_1 = {
    "total": 3,
    "data": [
        {"lens_id": "001-111-111-111-111", "title": "AI in Medical Education"},
        {"lens_id": "002-222-222-222-222", "title": "Simulation Training"},
    ],
}

SEARCH_PAGE_2 = {
    "total": 3,
    "data": [
        {"lens_id": "003-333-333-333-333", "title": "Medical Education Analytics"},
    ],
}

FETCH_RECORD = {
    "lens_id": "001-111-111-111-111",
    "title": "AI in Medical Education",
    "abstract": "A study on AI curriculum uptake.",
    "year_published": 2024,
    "publication_type": "journal article",
    "keywords": ["education", "AI"],
    "external_ids": [
        {"type": "doi", "value": "10.1001/JAMA.2024.0001"},
        {"type": "pmid", "value": "26082390"},
        {"type": "pmcid", "value": "PMC5024789"},
        {"type": "coreid", "value": "123456"},
        {"type": "openalex", "value": "W123456789"},
        {"type": "magid", "value": "987654321"},
    ],
    "source": {
        "title": "Journal of Medical Education",
        "issn": [{"value": "10797114", "type": "print"}],
    },
    "authors": [
        {
            "first_name": "Jane",
            "last_name": "Doe",
            "ids": [
                {"type": "orcid", "value": "https://orcid.org/0000-0001-2345-6789"},
            ],
            "affiliations": [{"name": "University Medical Center"}],
        },
        {
            "first_name": "John",
            "last_name": "Roe",
            "ids": [],
            "affiliations": [],
        },
    ],
    "mesh_terms": [
        {"mesh_id": "D000001", "mesh_heading": "Artificial Intelligence"},
        {"mesh_id": "D000002", "mesh_heading": "Medical Education"},
    ],
    "references": [
        {"lens_id": "011-222-333-444-555"},
        {"text": "Some old style reference"},
    ],
}


def _mock_resp(payload):
    resp = AsyncMock()
    resp.json.return_value = payload
    resp.raise_for_status = lambda: None
    return resp


@pytest.fixture
def adapter():
    test_value = "lens-" + "test-token"
    return LensAdapter(api_key=test_value)


def test_metadata():
    a = LensAdapter()
    assert a.name == "lens"
    assert a.display_name == "Lens.org"
    assert a.requires_api_key is True


def test_api_key_is_sent_as_bearer_token():
    test_value = "lens-" + "test-token"
    adapter = LensAdapter(api_key=test_value)

    assert adapter._client.headers["Authorization"] == "Bearer lens-test-token"


def test_methodology_label():
    assert LensAdapter().methodology_label() == "Lens.org Scholarly API"


def test_search(adapter: LensAdapter):
    payload = _mock_resp(SEARCH_PAGE_1)
    with patch.object(adapter._client, "post", return_value=payload):
        result = asyncio.run(adapter.search("medical education"))
    assert isinstance(result, SearchResponse)
    assert result.total_count == 3
    assert result.ids == ["001-111-111-111-111", "002-222-222-222-222"]


def test_search_treats_not_found_as_empty_result(adapter: LensAdapter):
    response = httpx.Response(
        status_code=404,
        request=httpx.Request("POST", f"{lens_module.LENS_API}/scholarly/search"),
    )

    with patch.object(adapter._client, "post", return_value=response):
        result = asyncio.run(adapter.search("query with no matches"))

    assert result == SearchResponse(total_count=0, ids=[])


def test_search_ignores_records_without_lens_ids(adapter: LensAdapter):
    response = {"total": 2, "data": [{"title": "Missing ID"}, SEARCH_PAGE_1["data"][0]]}
    with patch.object(adapter._client, "post", return_value=_mock_resp(response)):
        result = asyncio.run(adapter.search("medical education"))

    assert result.ids == ["001-111-111-111-111"]


def test_search_rejects_malformed_top_level_response(adapter: LensAdapter):
    with patch.object(adapter._client, "post", return_value=_mock_resp([])):
        with pytest.raises(ValueError, match="Lens API returned an invalid response"):
            asyncio.run(adapter.search("medical education"))


def test_search_applies_year_filter(adapter: LensAdapter):
    captured = {}

    async def capturing_post(url, json=None):
        captured["payload"] = json
        return _mock_resp(SEARCH_PAGE_1)

    with patch.object(adapter._client, "post", side_effect=capturing_post):
        asyncio.run(adapter.search("education", year_start=2020, year_end=2024))

    assert captured["payload"]["query"]["bool"]["must"][1]["range"]["year_published"] == {
        "gte": "2020",
        "lte": "2024",
    }


def test_search_paginated_walks_pages(adapter: LensAdapter):
    call_count = 0
    offsets = []

    async def mock_post(url, json=None):
        nonlocal call_count
        call_count += 1
        offsets.append(json["from"])
        if call_count == 1:
            return _mock_resp(SEARCH_PAGE_1)
        if call_count == 2:
            return _mock_resp(SEARCH_PAGE_2)
        return _mock_resp({"total": 3, "data": []})

    with patch.object(adapter._client, "post", side_effect=mock_post):
        batches = []

        async def run():
            async for batch in adapter.search_paginated("education"):
                batches.append(batch)

        asyncio.run(run())

    assert batches == [
        ["001-111-111-111-111", "002-222-222-222-222"],
        ["003-333-333-333-333"],
    ]
    assert offsets == [0, 2]


def test_search_paginated_stops_at_lens_offset_limit(adapter: LensAdapter, monkeypatch):
    monkeypatch.setattr(lens_module, "_MAX_OFFSET_RESULTS", 2)
    response = {"total": 3, "data": SEARCH_PAGE_1["data"]}

    with patch.object(adapter._client, "post", return_value=_mock_resp(response)) as post:
        async def run():
            return [batch async for batch in adapter.search_paginated("education")]

        batches = asyncio.run(run())

    assert batches == [["001-111-111-111-111", "002-222-222-222-222"]]
    post.assert_called_once()


def test_fetch_maps_to_raw_record(adapter: LensAdapter):
    with patch.object(adapter._client, "post", return_value=_mock_resp({"data": [FETCH_RECORD]})):
        records = asyncio.run(adapter.fetch(["001-111-111-111-111"]))

    assert len(records) == 1
    record = records[0]
    assert isinstance(record, RawRecord)
    assert record.source_database == "lens"
    assert record.source_id == "001-111-111-111-111"
    assert record.title == "AI in Medical Education"
    assert record.abstract == "A study on AI curriculum uptake."
    assert record.year == 2024
    assert record.doi == "10.1001/jama.2024.0001"
    assert record.external_ids["doi"] == "10.1001/jama.2024.0001"
    assert record.external_ids["pmid"] == "26082390"
    assert record.external_ids["pmcid"] == "PMC5024789"
    assert record.external_ids["coreid"] == "123456"
    assert record.external_ids["openalex"] == "W123456789"
    assert record.external_ids["magid"] == "987654321"
    assert record.external_ids["lens_id"] == "001-111-111-111-111"
    assert record.journal_name == "Journal of Medical Education"
    assert record.journal_issn == "10797114"
    assert record.publication_type == "journal article"
    assert [a.name for a in record.authors] == ["Jane Doe", "John Roe"]
    assert record.authors[0].orcid == "0000-0001-2345-6789"
    assert record.authors[0].affiliation == "University Medical Center"
    assert record.authors[1].orcid is None
    assert record.mesh_terms == ["Artificial Intelligence", "Medical Education"]
    assert record.keywords == ["education", "AI"]
    assert record.references == ["011-222-333-444-555"]


def test_fetch_normalizes_prefixed_doi(adapter: LensAdapter):
    record = {
        **FETCH_RECORD,
        "external_ids": [{"type": "doi", "value": "DOI:10.1001/JAMA.2024.0001"}],
    }
    with patch.object(adapter._client, "post", return_value=_mock_resp({"data": [record]})):
        records = asyncio.run(adapter.fetch(["001-111-111-111-111"]))

    assert records[0].doi == "10.1001/jama.2024.0001"


def test_fetch_empty_ids_avoids_api_call(adapter: LensAdapter):
    with patch.object(adapter._client, "post") as post:
        records = asyncio.run(adapter.fetch([]))

    assert records == []
    post.assert_not_called()


def test_fetch_ignores_records_without_valid_lens_ids(adapter: LensAdapter):
    response = {"data": [{"title": "Missing ID"}, {"lens_id": 123}, FETCH_RECORD]}
    with patch.object(adapter._client, "post", return_value=_mock_resp(response)):
        records = asyncio.run(adapter.fetch(["001-111-111-111-111"]))

    assert [record.source_id for record in records] == ["001-111-111-111-111"]


def test_fetch_uses_author_display_name_and_publication_date_fallback(adapter: LensAdapter):
    record = {
        **FETCH_RECORD,
        "year_published": None,
        "date_published": "2023-07-14T00:00:00.000000+00:00",
        "authors": [{"display_name": "Ada Lovelace", "ids": [], "affiliations": []}],
    }
    with patch.object(adapter._client, "post", return_value=_mock_resp({"data": [record]})):
        records = asyncio.run(adapter.fetch(["001-111-111-111-111"]))

    assert records[0].year == 2023
    assert [author.name for author in records[0].authors] == ["Ada Lovelace"]


def test_fetch_rejects_malformed_scalar_metadata_without_failing_batch(adapter: LensAdapter):
    record = {
        **FETCH_RECORD,
        "title": ["not", "a", "string"],
        "abstract": {"unexpected": "shape"},
        "keywords": "not-a-list",
        "authors": [
            {"first_name": 123, "last_name": None, "ids": [], "affiliations": []},
            {"display_name": "Grace Hopper", "ids": [], "affiliations": []},
        ],
    }
    with patch.object(adapter._client, "post", return_value=_mock_resp({"data": [record]})):
        records = asyncio.run(adapter.fetch(["001-111-111-111-111"]))

    assert records[0].title == ""
    assert records[0].abstract is None
    assert records[0].keywords == []
    assert [author.name for author in records[0].authors] == ["Grace Hopper"]


def test_close_releases_http_client(adapter: LensAdapter):
    asyncio.run(adapter.close())

    assert adapter._client.is_closed
