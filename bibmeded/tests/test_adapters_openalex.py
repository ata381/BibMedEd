import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from app.adapters.openalex import OpenAlexAdapter
from app.adapters.base import RawRecord, SearchResponse


@pytest.fixture
def adapter():
    return OpenAlexAdapter()


SEARCH_RESPONSE_PAGE1 = {
    "meta": {"count": 3, "per_page": 2},
    "results": [
        {"id": "https://openalex.org/W1", "ids": {"openalex": "W1", "pmid": "https://pubmed.ncbi.nlm.nih.gov/11111", "doi": "https://doi.org/10.1/a"}},
        {"id": "https://openalex.org/W2", "ids": {"openalex": "W2", "doi": "https://doi.org/10.1/b"}},
    ],
    "next_cursor": "abc123",
}

SEARCH_RESPONSE_PAGE2 = {
    "meta": {"count": 3, "per_page": 2},
    "results": [
        {"id": "https://openalex.org/W3", "ids": {"openalex": "W3"}},
    ],
    "next_cursor": None,
}

WORK_DETAIL = {
    "id": "https://openalex.org/W1",
    "title": "AI in Medical Education",
    "ids": {"openalex": "W1", "pmid": "https://pubmed.ncbi.nlm.nih.gov/11111", "doi": "https://doi.org/10.1/a"},
    "publication_year": 2024,
    "primary_location": {
        "source": {"display_name": "BMJ", "issn_l": "0959-8138"},
    },
    "type": "article",
    "authorships": [
        {
            "author": {"display_name": "Jane Doe", "orcid": "https://orcid.org/0000-0001-2345-6789"},
            "institutions": [{"display_name": "Harvard Medical School", "country_code": "US"}],
        },
    ],
    "keywords": [{"display_name": "medical education"}],
    "concepts": [{"display_name": "Artificial Intelligence"}],
    "referenced_works": ["https://openalex.org/W99"],
    "abstract_inverted_index": {"AI": [0], "is": [1], "great": [2]},
    "cited_by_count": 42,
}


def test_openalex_metadata():
    a = OpenAlexAdapter()
    assert a.name == "openalex"
    assert a.display_name == "OpenAlex"
    assert a.requires_api_key is False


def test_openalex_search(adapter):
    mock_resp = AsyncMock()
    mock_resp.json.return_value = SEARCH_RESPONSE_PAGE1
    mock_resp.raise_for_status = lambda: None
    with patch.object(adapter._client, "get", return_value=mock_resp):
        result = asyncio.run(adapter.search("AI medical education"))
    assert isinstance(result, SearchResponse)
    assert result.total_count == 3
    assert result.ids == ["W1", "W2"]


def test_openalex_search_paginated(adapter):
    page1_resp = AsyncMock()
    page1_resp.json.return_value = SEARCH_RESPONSE_PAGE1
    page1_resp.raise_for_status = lambda: None

    page2_resp = AsyncMock()
    page2_resp.json.return_value = SEARCH_RESPONSE_PAGE2
    page2_resp.raise_for_status = lambda: None

    call_count = 0
    async def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return page1_resp
        return page2_resp

    with patch.object(adapter._client, "get", side_effect=mock_get):
        batches = []
        async def run():
            async for batch in adapter.search_paginated("test"):
                batches.append(batch)
        asyncio.run(run())
    assert len(batches) == 2
    assert batches[0] == ["W1", "W2"]
    assert batches[1] == ["W3"]


def test_openalex_fetch(adapter):
    mock_resp = AsyncMock()
    mock_resp.json.return_value = {"results": [WORK_DETAIL]}
    mock_resp.raise_for_status = lambda: None
    with patch.object(adapter._client, "get", return_value=mock_resp):
        records = asyncio.run(adapter.fetch(["W1"]))
    assert len(records) == 1
    r = records[0]
    assert isinstance(r, RawRecord)
    assert r.source_id == "W1"
    assert r.source_database == "openalex"
    assert r.title == "AI in Medical Education"
    assert r.year == 2024
    assert r.journal_name == "BMJ"
    assert r.external_ids["openalex"] == "W1"
    assert r.external_ids["pmid"] == "11111"
    assert r.external_ids["doi"] == "10.1/a"
    assert r.doi == "10.1/a"
    assert len(r.authors) == 1
    assert r.authors[0].name == "Jane Doe"
    assert r.authors[0].orcid == "0000-0001-2345-6789"
    assert r.authors[0].affiliation == "Harvard Medical School"
    assert r.keywords == ["medical education"]
    assert "AI is great" == r.abstract


def test_openalex_methodology_label():
    a = OpenAlexAdapter()
    assert a.methodology_label() == "OpenAlex API"
