from app.models import Publication, SearchProject, SearchQuery

def test_run_publication_analysis(client, db):
    project = SearchProject(name="Test")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="test")
    db.add(query)
    db.flush()
    for i in range(3):
        db.add(Publication(pmid=f"anal{i}", title=f"P{i}", year=2024, query_id=query.id))
    db.commit()
    response = client.post(f"/api/projects/{project.id}/analysis/publications")
    assert response.status_code == 200
    data = response.json()
    assert data["analysis_type"] == "publications"
    assert data["results"]["total"] == 3

def test_get_cached_analysis(client, db):
    project = SearchProject(name="Test2")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="test")
    db.add(query)
    db.flush()
    db.add(Publication(pmid="cache1", title="P1", year=2024, query_id=query.id))
    db.commit()
    # Run analysis first
    client.post(f"/api/projects/{project.id}/analysis/publications")
    # Get cached result
    response = client.get(f"/api/projects/{project.id}/analysis/publications")
    assert response.status_code == 200
    assert response.json()["results"]["total"] == 1

def test_unknown_analysis_type(client, db):
    project = SearchProject(name="Test3")
    db.add(project)
    db.commit()
    response = client.post(f"/api/projects/{project.id}/analysis/unknown")
    assert response.status_code == 400

def test_analysis_not_found(client, db):
    project = SearchProject(name="Test4")
    db.add(project)
    db.commit()
    response = client.get(f"/api/projects/{project.id}/analysis/publications")
    assert response.status_code == 404
