import asyncio
import pytest
from app.adapters.base import RawAuthor, RawRecord, SearchResponse, BaseSourceAdapter


def test_raw_author_defaults():
    a = RawAuthor(name="Smith, John")
    assert a.name == "Smith, John"
    assert a.orcid is None
    assert a.affiliation is None


def test_raw_record_defaults():
    r = RawRecord(source_id="123", source_database="test", title="Test Paper")
    assert r.source_id == "123"
    assert r.source_database == "test"
    assert r.title == "Test Paper"
    assert r.abstract is None
    assert r.doi is None
    assert r.year is None
    assert r.authors == []
    assert r.mesh_terms == []
    assert r.keywords == []
    assert r.references == []
    assert r.external_ids == {}


def test_raw_record_with_external_ids():
    r = RawRecord(
        source_id="123", source_database="pubmed", title="Test",
        external_ids={"pmid": "123", "doi": "10.1000/test"},
    )
    assert r.external_ids["pmid"] == "123"
    assert r.external_ids["doi"] == "10.1000/test"


def test_search_response():
    s = SearchResponse(total_count=100, ids=["1", "2", "3"])
    assert s.total_count == 100
    assert len(s.ids) == 3


def test_base_adapter_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseSourceAdapter()


class _StubAdapter(BaseSourceAdapter):
    name = "stub"
    display_name = "Stub"
    requires_api_key = False

    async def search(self, query, **kwargs):
        return SearchResponse(total_count=3, ids=["a", "b", "c"])

    async def fetch(self, ids):
        return [RawRecord(source_id=i, source_database="stub", title=f"Paper {i}") for i in ids]


def test_default_search_paginated():
    adapter = _StubAdapter()
    batches = []
    async def run():
        async for batch in adapter.search_paginated("test"):
            batches.append(batch)
    asyncio.run(run())
    assert len(batches) == 1
    assert batches[0] == ["a", "b", "c"]


def test_default_fetch_stream():
    adapter = _StubAdapter()
    chunks = []
    async def run():
        async for chunk in adapter.fetch_stream(["a", "b", "c", "d", "e"], batch_size=2):
            chunks.append(chunk)
    asyncio.run(run())
    assert len(chunks) == 3
    assert len(chunks[0]) == 2
    assert len(chunks[2]) == 1


def test_default_methodology_label():
    adapter = _StubAdapter()
    assert adapter.methodology_label() == "Stub API"


def test_default_close():
    adapter = _StubAdapter()
    asyncio.run(adapter.close())
