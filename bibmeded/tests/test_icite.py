import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from app.services.icite import ICiteClient

@pytest.fixture
def sample_response():
    return json.loads(Path("tests/fixtures/icite_response.json").read_text())

@pytest.fixture
def icite_client():
    return ICiteClient()

@pytest.mark.asyncio
async def test_get_citation_counts(icite_client, sample_response):
    mock_response = AsyncMock()
    mock_response.json = lambda: sample_response
    mock_response.raise_for_status = lambda: None
    with patch.object(icite_client._client, "get", return_value=mock_response):
        result = await icite_client.get_citations(["38000001", "38000002"])
    assert result["38000001"] == 45
    assert result["38000002"] == 12

@pytest.mark.asyncio
async def test_get_citation_counts_empty(icite_client):
    result = await icite_client.get_citations([])
    assert result == {}
