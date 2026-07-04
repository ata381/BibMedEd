from app.models import Keyword, KeywordType, Publication, SearchProject, SearchQuery
from app.analysis.keywords import analyze_keywords

def test_keyword_analysis(db):
    project = SearchProject(name="Test")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="test")
    db.add(query)
    db.flush()
    kw1 = Keyword(term="AI", type=KeywordType.mesh_term, term_normalized="ai")
    kw2 = Keyword(term="Education", type=KeywordType.mesh_term, term_normalized="education")
    pub1 = Publication(pmid="kw1", title="P1", year=2024, query_id=query.id, project_id=project.id)
    pub1.keywords.extend([kw1, kw2])
    pub2 = Publication(pmid="kw2", title="P2", year=2024, query_id=query.id, project_id=project.id)
    pub2.keywords.append(kw1)
    db.add_all([pub1, pub2])
    db.commit()
    result = analyze_keywords(db, project.id)
    assert len(result["top_keywords"]) >= 2
    assert result["top_keywords"][0]["term"] == "AI"
    assert result["top_keywords"][0]["count"] == 2
    assert len(result["cooccurrence_network"]["links"]) >= 1


def test_keyword_analysis_normalizes_keyword_case(db):
    project = SearchProject(name="Case")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="case")
    db.add(query)
    db.flush()

    kw_upper = Keyword(term="AI", type=KeywordType.mesh_term, term_normalized="ai")
    kw_lower = Keyword(term="ai", type=KeywordType.mesh_term, term_normalized="ai")
    pub1 = Publication(pmid="kcase1", title="P1", year=2024, query_id=query.id, project_id=project.id)
    pub1.keywords.append(kw_upper)
    pub2 = Publication(pmid="kcase2", title="P2", year=2025, query_id=query.id, project_id=project.id)
    pub2.keywords.append(kw_lower)
    db.add_all([pub1, pub2])
    db.commit()

    result = analyze_keywords(db, project.id)
    assert result["top_keywords"][0]["count"] == 2
    assert result["top_keywords"][0]["term"].lower() == "ai"
