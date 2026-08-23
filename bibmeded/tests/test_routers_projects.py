from unittest.mock import Mock

from sqlalchemy.exc import IntegrityError


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


def test_create_sample_project_populates_a_complete_offline_workflow(client):
    response = client.post("/api/projects/sample")

    assert response.status_code == 201
    project = response.json()
    assert project["name"] == "AI in Medical Education — Sample Project"
    assert "synthetic" in project["description"].lower()

    project_id = project["id"]
    publications = client.get(f"/api/projects/{project_id}/publications")
    assert publications.status_code == 200
    publication_data = publications.json()
    assert publication_data["total"] == 12
    assert publication_data["excluded_count"] == 1

    latest_search = client.get(f"/api/projects/{project_id}/search/latest")
    assert latest_search.status_code == 200
    latest_search_data = latest_search.json()
    assert latest_search_data["status"] == "completed"
    assert latest_search_data["result_count"] == 12
    assert latest_search_data["raw_result_count"] == 13
    assert latest_search_data["duplicate_count"] == 1
    assert latest_search_data["progress"] == 100

    expected_analysis_signals = {
        "publications": lambda data: data["total"] == 11 and len(data["yearly_counts"]) >= 5,
        "authors": lambda data: data["total_authors"] >= 6 and bool(data["coauthorship_network"]["links"]),
        "countries": lambda data: len(data["country_counts"]) >= 3 and bool(data["collaboration_network"]["links"]),
        "keywords": lambda data: len(data["top_keywords"]) >= 5 and bool(data["cooccurrence_network"]["links"]),
        "citations": lambda data: data["total_citations"] > 0 and bool(data["coupling_network"]["links"]),
        "journals": lambda data: data["total_journals"] >= 3 and bool(data["bradford_zones"]),
    }
    for analysis_type, has_signal in expected_analysis_signals.items():
        analysis = client.post(f"/api/projects/{project_id}/analysis/{analysis_type}")
        assert analysis.status_code == 200
        results = analysis.json()["results"]
        assert results["schema_version"] == "1.0"
        assert has_signal(results), f"sample {analysis_type} analysis was not meaningful: {results}"

    methodology = client.get(f"/api/projects/{project_id}/export/methodology")
    assert methodology.status_code == 200
    assert "synthetic demonstration dataset" in methodology.text.lower()


def test_create_sample_project_reuses_the_bundled_corpus(client):
    first_response = client.post("/api/projects/sample")
    second_response = client.post("/api/projects/sample")

    assert first_response.status_code == 201
    assert second_response.status_code == 200
    first = first_response.json()
    second = second_response.json()

    assert first["id"] == second["id"]
    projects = client.get("/api/projects").json()
    sample_projects = [project for project in projects if project["name"] == first["name"]]
    assert len(sample_projects) == 1

    normal_project = client.post("/api/projects", json={"name": "Created after sample"})
    assert normal_project.status_code == 201
    assert normal_project.json()["id"] > 0


def test_create_sample_project_can_be_deleted_and_reset(client):
    first = client.post("/api/projects/sample").json()

    deleted = client.delete(f"/api/projects/{first['id']}")
    assert deleted.status_code == 204

    recreated = client.post("/api/projects/sample")
    assert recreated.status_code == 201
    assert recreated.json()["id"] == first["id"]
    publications = client.get(f"/api/projects/{first['id']}/publications")
    assert publications.json()["total"] == 12


def test_sample_project_recovers_when_another_process_creates_it(monkeypatch):
    from app.services import sample_project

    concurrent_project = Mock()
    db = Mock()
    duplicate = IntegrityError("insert sample", {}, Exception("duplicate sample key"))
    monkeypatch.setattr(
        sample_project,
        "_find_sample_project",
        Mock(side_effect=[None, concurrent_project]),
    )
    monkeypatch.setattr(
        sample_project,
        "_create_sample_project",
        Mock(side_effect=duplicate),
    )

    project, created = sample_project.get_or_create_sample_project(db)

    assert project is concurrent_project
    assert created is False
    db.rollback.assert_called()


def test_sample_project_openapi_documents_create_and_reuse_responses(client):
    responses = client.get("/openapi.json").json()["paths"]["/api/projects/sample"]["post"]["responses"]

    assert {"200", "201"}.issubset(responses)


def test_openapi_reports_current_release_version(client):
    assert client.get("/openapi.json").json()["info"]["version"] == "0.3.0"
