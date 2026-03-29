import asyncio
from unittest.mock import AsyncMock, patch
from pathlib import Path
import pytest
from app.adapters.pubmed import PubMedAdapter
from app.adapters.base import RawRecord, SearchResponse


@pytest.fixture
def adapter():
    return PubMedAdapter(api_key="", rate_limit=10.0)


@pytest.fixture
def sample_xml():
    return Path("tests/fixtures/pubmed_response.xml").read_text()


def test_pubmed_adapter_metadata():
    a = PubMedAdapter()
    assert a.name == "pubmed"
    assert a.display_name == "PubMed"
    assert a.requires_api_key is False


def test_pubmed_search(adapter):
    mock_response = AsyncMock()
    mock_response.text = '<?xml version="1.0"?><eSearchResult><Count>2</Count><IdList><Id>38000001</Id><Id>38000002</Id></IdList></eSearchResult>'
    mock_response.raise_for_status = lambda: None
    with patch.object(adapter._client._client, "get", return_value=mock_response):
        result = asyncio.run(adapter.search("test query"))
    assert isinstance(result, SearchResponse)
    assert result.total_count == 2
    assert result.ids == ["38000001", "38000002"]


def test_pubmed_fetch_returns_raw_records(adapter, sample_xml):
    mock_response = AsyncMock()
    mock_response.text = sample_xml
    mock_response.raise_for_status = lambda: None
    with patch.object(adapter._client._client, "get", return_value=mock_response):
        records = asyncio.run(adapter.fetch(["38000001"]))
    assert len(records) == 1
    r = records[0]
    assert isinstance(r, RawRecord)
    assert r.source_id == "38000001"
    assert r.source_database == "pubmed"
    assert r.title == "Machine Learning in Medical Education: A Systematic Review"
    assert r.external_ids["pmid"] == "38000001"
    assert "doi" in r.external_ids
    assert len(r.authors) == 2
    assert r.authors[0].name == "Smith, John"
    assert r.keywords == ["machine learning", "medical education"]
    assert len(r.mesh_terms) == 2


def test_pubmed_fetch_no_doi():
    adapter = PubMedAdapter(api_key="", rate_limit=10.0)
    from app.services.pubmed import PubMedRecord
    record = PubMedRecord(pmid="99999", title="No DOI Paper")
    raw = adapter._to_raw(record)
    assert raw.external_ids == {"pmid": "99999"}
    assert "doi" not in raw.external_ids


def test_pubmed_methodology_label():
    a = PubMedAdapter()
    assert a.methodology_label() == "PubMed E-Utilities"


def test_pubmed_close(adapter):
    asyncio.run(adapter.close())
    assert adapter._client._client.is_closed
