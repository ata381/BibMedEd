from app.models import Author, Publication, SearchProject, SearchQuery
from app.analysis.authors import analyze_authors

def test_author_analysis(db):
    project = SearchProject(name="Test")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="test")
    db.add(query)
    db.flush()
    a1 = Author(name="Smith, John", name_normalized="smith john")
    a2 = Author(name="Chen, Li", name_normalized="chen li")
    a3 = Author(name="Patel, Raj", name_normalized="patel raj")
    pub1 = Publication(pmid="auth1", title="Paper 1", year=2024, citation_count=10, query_id=query.id)
    pub1.authors.extend([a1, a2])
    pub2 = Publication(pmid="auth2", title="Paper 2", year=2024, citation_count=5, query_id=query.id)
    pub2.authors.extend([a1, a3])
    db.add_all([pub1, pub2])
    db.commit()
    result = analyze_authors(db, project.id)
    assert result["total_authors"] == 3
    assert result["top_authors"][0]["name"] == "Smith, John"
    assert result["top_authors"][0]["pub_count"] == 2
    assert len(result["coauthorship_network"]["nodes"]) == 3

def test_author_analysis_empty(db):
    project = SearchProject(name="Empty")
    db.add(project)
    db.commit()
    result = analyze_authors(db, project.id)
    assert result["total_authors"] == 0
