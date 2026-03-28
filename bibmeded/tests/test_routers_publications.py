from app.models import Author, Journal, Publication, SearchProject, SearchQuery

def test_list_publications(client, db):
    project = SearchProject(name="Test")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="test")
    db.add(query)
    db.flush()
    journal = Journal(name="Test Journal")
    db.add(journal)
    db.flush()
    pub = Publication(pmid="11111111", title="Test Paper", year=2024, journal_id=journal.id, query_id=query.id)
    author = Author(name="Smith, John")
    pub.authors.append(author)
    db.add(pub)
    db.commit()
    response = client.get(f"/api/projects/{project.id}/publications")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert data["items"][0]["title"] == "Test Paper"

def test_list_publications_with_sort(client, db):
    project = SearchProject(name="Sort Test")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="test")
    db.add(query)
    db.flush()
    for i, year in enumerate([2023, 2024, 2022]):
        pub = Publication(pmid=f"sort{i}", title=f"Paper {i}", year=year, query_id=query.id)
        db.add(pub)
    db.commit()
    response = client.get(f"/api/projects/{project.id}/publications?sort_by=year&order=asc")
    years = [p["year"] for p in response.json()["items"]]
    assert years == sorted(years)
