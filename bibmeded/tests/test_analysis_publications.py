from app.models import Publication, SearchProject, SearchQuery
from app.analysis.publications import analyze_publication_trends

def test_publication_trends(db):
    project = SearchProject(name="Test")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="test")
    db.add(query)
    db.flush()
    for i, year in enumerate([2022, 2022, 2023, 2023, 2023, 2024]):
        db.add(Publication(pmid=f"trend{i}", title=f"P{i}", year=year, query_id=query.id))
    db.commit()
    result = analyze_publication_trends(db, project.id)
    assert result["total"] == 6
    assert len(result["yearly_counts"]) == 3
    assert result["yearly_counts"][0] == {"year": 2022, "count": 2}
    assert len(result["cumulative"]) == 3
    assert result["cumulative"][-1]["cumulative"] == 6

def test_publication_trends_empty(db):
    project = SearchProject(name="Empty")
    db.add(project)
    db.commit()
    result = analyze_publication_trends(db, project.id)
    assert result["total"] == 0
