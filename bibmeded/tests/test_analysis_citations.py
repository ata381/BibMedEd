from app.models import Publication, SearchProject, SearchQuery
from app.analysis.citations import analyze_citations


def test_citation_analysis(db):
    project = SearchProject(name="Test")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="test")
    db.add(query)
    db.flush()
    pub1 = Publication(pmid="cite1", title="Highly Cited", year=2023, citation_count=50, query_id=query.id, project_id=project.id)
    pub2 = Publication(pmid="cite2", title="Less Cited", year=2024, citation_count=5, query_id=query.id, project_id=project.id)
    db.add_all([pub1, pub2])
    db.commit()
    result = analyze_citations(db, project.id)
    assert result["total_citations"] == 55
    assert result["most_cited"][0]["citation_count"] == 50
    assert result["most_cited"][0]["title"] == "Highly Cited"
    # Empty in-corpus reference data → both new networks empty.
    assert result["coupling_network"]["links"] == []
    assert result["cocitation_network"]["links"] == []


def test_bibliographic_coupling_pairs_shared_refs(db):
    """Two papers that both cite the same in-corpus paper should appear coupled."""
    project = SearchProject(name="Coupling")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="t")
    db.add(query)
    db.flush()
    seminal = Publication(pmid="seminal_pmid", doi="10.1/seminal", title="Seminal", year=2010, citation_count=500, query_id=query.id, project_id=project.id)
    citer_a = Publication(pmid="a", doi="10.1/a", title="A", year=2022, citation_count=5, query_id=query.id, project_id=project.id,
                          external_references=["10.1/seminal", "10.1/other_external"])
    citer_b = Publication(pmid="b", doi="10.1/b", title="B", year=2023, citation_count=3, query_id=query.id, project_id=project.id,
                          external_references=["10.1/SEMINAL", "10.1/different_external"])
    db.add_all([seminal, citer_a, citer_b])
    db.commit()
    result = analyze_citations(db, project.id)
    coupling = result["coupling_network"]
    # citer_a and citer_b both cite `seminal` → exactly one coupling edge between them.
    assert len(coupling["links"]) == 1
    edge = coupling["links"][0]
    assert edge["weight"] == 1


def test_cocitation_pairs_when_citer_lists_multiple_in_corpus_refs(db):
    """Paper C that cites both A and B should produce a co-citation edge between A and B."""
    project = SearchProject(name="Cocitation")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="t")
    db.add(query)
    db.flush()
    a = Publication(pmid="A", doi="10.1/a", title="A", year=2010, citation_count=100, query_id=query.id, project_id=project.id)
    b = Publication(pmid="B", doi="10.1/b", title="B", year=2010, citation_count=100, query_id=query.id, project_id=project.id)
    c = Publication(pmid="C", title="C", year=2022, citation_count=1, query_id=query.id, project_id=project.id,
                    external_references=["10.1/a", "10.1/b"])
    db.add_all([a, b, c])
    db.commit()
    result = analyze_citations(db, project.id)
    cocitation = result["cocitation_network"]
    assert len(cocitation["links"]) == 1
    edge = cocitation["links"][0]
    assert edge["weight"] == 1
