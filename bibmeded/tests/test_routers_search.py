from unittest.mock import patch

from app.config import settings
from app.models import SearchProject

def test_trigger_search(client, db):
    project = SearchProject(name="Test")
    db.add(project)
    db.commit()
    db.refresh(project)
    with patch("app.routers.search.run_search") as mock_task:
        mock_task.delay.return_value = None
        response = client.post(f"/api/projects/{project.id}/search", json={"query_string": '"AI" AND "medical education"'})
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "pending"
    assert data["query_id"] is not None
    mock_task.delay.assert_called_once()

def test_trigger_search_forwards_request_id_to_run_search_task(client, db):
    """The dispatch site must propagate the inbound x-request-id so the Celery
    task can log/record it, honoring the documented API->Celery correlation."""
    project = SearchProject(name="Test")
    db.add(project)
    db.commit()
    db.refresh(project)
    with patch("app.routers.search.run_search") as mock_task:
        mock_task.delay.return_value = None
        response = client.post(
            f"/api/projects/{project.id}/search",
            json={"query_string": "test"},
            headers={"x-request-id": "corr-id-999"},
        )
    assert response.status_code == 202
    mock_task.delay.assert_called_once()
    args, kwargs = mock_task.delay.call_args
    assert "corr-id-999" in args or kwargs.get("request_id") == "corr-id-999"


def test_trigger_search_accepts_lens_source(client, db, monkeypatch):
    monkeypatch.setattr(settings, "lens_api_key", "lens-test-token")
    project = SearchProject(name="Lens Project")
    db.add(project)
    db.commit()
    db.refresh(project)

    with patch("app.routers.search.run_search") as mock_task:
        response = client.post(
            f"/api/projects/{project.id}/search",
            json={"query_string": "medical education", "source": "lens"},
        )

    assert response.status_code == 202
    assert mock_task.delay.call_args.args[1] == "lens"


def test_trigger_search_rejects_lens_when_api_key_is_missing(client, db, monkeypatch):
    monkeypatch.setattr(settings, "lens_api_key", "")
    project = SearchProject(name="Lens Project")
    db.add(project)
    db.commit()
    db.refresh(project)

    with patch("app.routers.search.run_search") as mock_task:
        response = client.post(
            f"/api/projects/{project.id}/search",
            json={"query_string": "medical education", "source": "lens"},
        )

    assert response.status_code == 503
    assert "BIBMEDED_LENS_API_KEY" in response.json()["detail"]
    mock_task.delay.assert_not_called()


def test_get_search_status(client, db):
    project = SearchProject(name="Test")
    db.add(project)
    db.commit()
    db.refresh(project)
    with patch("app.routers.search.run_search") as mock_task:
        mock_task.delay.return_value = None
        create = client.post(f"/api/projects/{project.id}/search", json={"query_string": "test"})
    query_id = create.json()["query_id"]
    response = client.get(f"/api/projects/{project.id}/search/{query_id}")
    assert response.status_code == 200
    assert response.json()["query_id"] == query_id
