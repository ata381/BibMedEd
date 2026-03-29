from unittest.mock import patch
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
