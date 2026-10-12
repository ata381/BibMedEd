import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from bibmeded.services.pubmed import PubMedClient


async def _capture_request(client: PubMedClient, operation: str) -> dict:
    fixture = "pubmed_search_response.xml" if operation == "search" else "pubmed_response.xml"
    response = AsyncMock()
    response.text = Path("tests/fixtures", fixture).read_text()
    response.raise_for_status = lambda: None
    async with client:
        with patch.object(client._client, "get", return_value=response) as get_mock:
            if operation == "search":
                await client.search("medical education")
            else:
                await client.fetch(["38000001"])
    return get_mock.call_args.kwargs["params"]


@pytest.mark.parametrize("operation", ["search", "fetch"])
async def test_request_identifies_tool_without_email(operation):
    params = await _capture_request(PubMedClient(), operation)
    assert params["tool"] == "bibmeded"
    assert "email" not in params


@pytest.mark.parametrize("operation", ["search", "fetch"])
@pytest.mark.parametrize("api_key", ["", " \t\n", " test-key "])
async def test_request_normalizes_optional_api_key(operation, api_key):
    params = await _capture_request(PubMedClient(api_key=api_key), operation)
    if api_key.strip():
        assert params["api_key"] == "test-key"
    else:
        assert "api_key" not in params


@pytest.mark.parametrize("operation", ["search", "fetch"])
@pytest.mark.parametrize("email", ["", " \t\n", " team@example.org "])
async def test_request_sends_only_configured_email(operation, email):
    params = await _capture_request(PubMedClient(email=email), operation)
    assert params["tool"] == "bibmeded"
    if email.strip():
        assert params["email"] == "team@example.org"
    else:
        assert "email" not in params

@pytest.fixture
def sample_xml():
    return Path("tests/fixtures/pubmed_response.xml").read_text()

@pytest.fixture
def pubmed_client():
    return PubMedClient(api_key="", rate_limit=10.0)

def test_search_returns_pmids(pubmed_client):
    mock_response = AsyncMock()
    mock_response.text = '<?xml version="1.0"?><eSearchResult><Count>2</Count><IdList><Id>38000001</Id><Id>38000002</Id></IdList></eSearchResult>'
    mock_response.raise_for_status = lambda: None
    with patch.object(pubmed_client._client, "get", return_value=mock_response):
        result = asyncio.run(pubmed_client.search('"artificial intelligence" AND "medical education"'))
    assert result.total_count == 2
    assert result.pmids == ["38000001", "38000002"]

def test_fetch_records(pubmed_client, sample_xml):
    mock_response = AsyncMock()
    mock_response.text = sample_xml
    mock_response.raise_for_status = lambda: None
    with patch.object(pubmed_client._client, "get", return_value=mock_response):
        records = asyncio.run(pubmed_client.fetch(["38000001"]))
    assert len(records) == 1
    assert records[0].pmid == "38000001"
    assert records[0].title == "Machine Learning in Medical Education: A Systematic Review"
    assert len(records[0].authors) == 2
    assert records[0].authors[0].name == "Smith, John"
    assert records[0].doi == "10.2196/12345"
    assert records[0].publication_type == "Review"
    assert records[0].author_keywords == ["machine learning", "medical education"]
    assert len(records[0].mesh_terms) == 2
    assert len(records[0].references) == 1


def test_client_async_context_manager():
    async def run():
        async with PubMedClient(api_key="", rate_limit=10.0) as client:
            assert client is not None
            assert not client._client.is_closed
        assert client._client.is_closed

    asyncio.run(run())


def test_fetch_returns_empty_list_when_pmids_empty(pubmed_client):
    with patch.object(pubmed_client._client, "get") as get_mock:
        records = asyncio.run(pubmed_client.fetch([]))
    assert records == []
    get_mock.assert_not_called()


def test_client_rejects_invalid_rate_limit():
    with pytest.raises(ValueError, match="rate_limit must be greater than 0"):
        PubMedClient(api_key="", rate_limit=0.0)
