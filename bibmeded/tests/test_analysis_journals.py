from app.models import Journal, Publication, SearchProject, SearchQuery
from app.analysis.journals import analyze_journals

def test_journal_analysis(db):
    project = SearchProject(name="Test")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="test")
    db.add(query)
    db.flush()
    j1 = Journal(name="JMIR Med Ed")
    j2 = Journal(name="Academic Medicine")
    db.add_all([j1, j2])
    db.flush()
    for i in range(5):
        db.add(Publication(pmid=f"j1_{i}", title=f"P{i}", year=2024, journal_id=j1.id, citation_count=10, query_id=query.id))
    for i in range(2):
        db.add(Publication(pmid=f"j2_{i}", title=f"Q{i}", year=2024, journal_id=j2.id, citation_count=5, query_id=query.id))
    db.commit()
    result = analyze_journals(db, project.id)
    assert result["total_journals"] == 2
    assert result["top_journals"][0]["name"] == "JMIR Med Ed"
    assert result["top_journals"][0]["pub_count"] == 5
    assert len(result["bradford_zones"]) >= 1
