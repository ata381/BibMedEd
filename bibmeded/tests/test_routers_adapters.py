def test_list_adapters(client):
    response = client.get("/api/adapters")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    pubmed = next(a for a in data if a["name"] == "pubmed")
    assert pubmed["display_name"] == "PubMed"
    assert pubmed["requires_api_key"] is False
