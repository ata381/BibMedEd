from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from app.services.pubmed import PubMedClient

@pytest.fixture
def sample_xml():
    return Path("tests/fixtures/pubmed_response.xml").read_text()

@pytest.fixture
def pubmed_client():
    return PubMedClient(api_key="", rate_limit=10.0)

@pytest.mark.asyncio
async def test_search_returns_pmids(pubmed_client):
    mock_response = AsyncMock()
    mock_response.text = '<?xml version="1.0"?><eSearchResult><Count>2</Count><IdList><Id>38000001</Id><Id>38000002</Id></IdList></eSearchResult>'
    mock_response.raise_for_status = lambda: None
    with patch.object(pubmed_client._client, "get", return_value=mock_response):
        result = await pubmed_client.search('"artificial intelligence" AND "medical education"')
    assert result.total_count == 2
    assert result.pmids == ["38000001", "38000002"]

@pytest.mark.asyncio
async def test_fetch_records(pubmed_client, sample_xml):
    mock_response = AsyncMock()
    mock_response.text = sample_xml
    mock_response.raise_for_status = lambda: None
    with patch.object(pubmed_client._client, "get", return_value=mock_response):
        records = await pubmed_client.fetch(["38000001"])
    assert len(records) == 1
    assert records[0].pmid == "38000001"
    assert records[0].title == "Machine Learning in Medical Education: A Systematic Review"
    assert len(records[0].authors) == 2
    assert records[0].authors[0].name == "Smith, John"
    assert records[0].doi == "10.2196/12345"
    assert len(records[0].mesh_terms) == 2
    assert len(records[0].references) == 1
