from app.models import Publication, SearchProject, SearchQuery
from app.analysis.citations import analyze_citations, _HUB_DEGREE_CAP


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
    # Nothing to truncate when there is no reference data at all.
    assert result["coupling_truncated"] is False
    assert result["cocitation_truncated"] is False


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


def test_hub_truncation_is_disclosed_and_prefers_high_degree_papers_over_low_ids(db):
    """A hub reference cited by more than `_HUB_DEGREE_CAP` in-corpus papers must

    (1) surface the truncation via `coupling_truncated` rather than silently
        dropping papers, and
    (2) select which papers to keep based on network connectivity (degree),
        not database-id order -- so a high-id, high-connectivity paper is not
        deterministically excluded just because of its insertion order.
    """
    project = SearchProject(name="HubTruncation")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="t")
    db.add(query)
    db.flush()

    seminal = Publication(
        pmid="seminal", doi="10.1/seminal", title="Seminal", year=2000,
        query_id=query.id, project_id=project.id,
    )
    other1 = Publication(pmid="other1", doi="10.1/other1", title="Other1", year=2001, query_id=query.id, project_id=project.id)
    other2 = Publication(pmid="other2", doi="10.1/other2", title="Other2", year=2002, query_id=query.id, project_id=project.id)
    db.add_all([seminal, other1, other2])
    db.flush()

    n_citers = _HUB_DEGREE_CAP + 5  # exceeds the cap so truncation must trigger
    citers = []
    for i in range(n_citers):
        citers.append(Publication(
            pmid=f"citer{i}", doi=f"10.1/citer{i}", title=f"Citer{i}", year=2020,
            query_id=query.id, project_id=project.id,
            external_references=["10.1/seminal"],
        ))
    db.add_all(citers)
    db.flush()

    # The LAST-inserted (highest id) citer is also the most connected paper in the
    # network: it additionally cites two other in-corpus papers, giving it the
    # highest reference-degree of any citer. Under the old ID-ordered slice this
    # paper would always be excluded (it has the highest id); a degree-aware
    # selection must keep it.
    high_degree_citer = citers[-1]
    high_degree_citer.external_references = ["10.1/seminal", "10.1/other1", "10.1/other2"]
    db.commit()

    result = analyze_citations(db, project.id)

    assert result["coupling_truncated"] is True

    coupling_nodes = {n["pmid"] for n in result["coupling_network"]["nodes"]}
    assert high_degree_citer.pmid in coupling_nodes
