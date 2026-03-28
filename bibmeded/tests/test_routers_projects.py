def test_create_project(client):
    response = client.post("/api/projects", json={"name": "AI in Medical Education", "description": "Bibliometric analysis", "date_range_start": "2022-01-01", "date_range_end": "2025-06-30"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "AI in Medical Education"
    assert data["id"] is not None

def test_list_projects(client):
    client.post("/api/projects", json={"name": "Project 1"})
    client.post("/api/projects", json={"name": "Project 2"})
    response = client.get("/api/projects")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2

def test_get_project(client):
    create = client.post("/api/projects", json={"name": "Test"})
    project_id = create.json()["id"]
    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Test"

def test_get_project_not_found(client):
    response = client.get("/api/projects/99999")
    assert response.status_code == 404

def test_delete_project(client):
    create = client.post("/api/projects", json={"name": "To Delete"})
    project_id = create.json()["id"]
    response = client.delete(f"/api/projects/{project_id}")
    assert response.status_code == 204
    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 404
