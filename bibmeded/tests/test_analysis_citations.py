from app.models import Publication, SearchProject, SearchQuery
from app.analysis.citations import analyze_citations

def test_citation_analysis(db):
    project = SearchProject(name="Test")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="test")
    db.add(query)
    db.flush()
    pub1 = Publication(pmid="cite1", title="Highly Cited", year=2023, citation_count=50, query_id=query.id)
    pub2 = Publication(pmid="cite2", title="Less Cited", year=2024, citation_count=5, query_id=query.id)
    db.add_all([pub1, pub2])
    db.commit()
    result = analyze_citations(db, project.id)
    assert result["total_citations"] == 55
    assert result["most_cited"][0]["citation_count"] == 50
    assert result["most_cited"][0]["title"] == "Highly Cited"
