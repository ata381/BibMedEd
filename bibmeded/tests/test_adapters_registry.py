import pytest
from app.adapters.registry import discover_adapters, get_adapter, list_adapters, _adapters


@pytest.fixture(autouse=True)
def reset_registry():
    _adapters.clear()
    yield
    _adapters.clear()


def test_discover_adapters_finds_pubmed():
    discover_adapters()
    assert "pubmed" in _adapters


def test_get_adapter_returns_instance():
    discover_adapters()
    adapter = get_adapter("pubmed")
    assert adapter.name == "pubmed"
    assert adapter.display_name == "PubMed"


def test_get_adapter_unknown_raises():
    discover_adapters()
    with pytest.raises(ValueError, match="Unknown adapter: nonexistent"):
        get_adapter("nonexistent")


def test_list_adapters_returns_metadata():
    discover_adapters()
    adapters = list_adapters()
    assert len(adapters) >= 1
    pubmed = next(a for a in adapters if a["name"] == "pubmed")
    assert pubmed["display_name"] == "PubMed"
    assert pubmed["requires_api_key"] is False
