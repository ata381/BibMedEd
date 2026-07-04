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
    pub1 = Publication(pmid="auth1", title="Paper 1", year=2024, citation_count=10, query_id=query.id, project_id=project.id)
    pub1.authors.extend([a1, a2])
    pub2 = Publication(pmid="auth2", title="Paper 2", year=2024, citation_count=5, query_id=query.id, project_id=project.id)
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


def test_compute_indices_classic_example():
    """[5,4,3,2,1] → h=3 (papers 1-3 each have >=3 citations), g=3
    (cumulative top-3 = 12 >= 9; cumulative top-4 = 14 < 16),
    e = sqrt(12 - 9) ≈ 1.73."""
    from app.analysis.authors import _compute_indices
    indices = _compute_indices([5, 4, 3, 2, 1], pub_count=5)
    assert indices["h_index"] == 3
    assert indices["g_index"] == 3
    assert indices["e_index"] == 1.73


def test_compute_indices_g_index_rewards_outliers():
    """g-index promotes one highly-cited paper. [20,1,1] → h=1 but g=3 (1*20+1+1=22 >= 9)."""
    from app.analysis.authors import _compute_indices
    indices = _compute_indices([20, 1, 1], pub_count=3)
    assert indices["h_index"] == 1
    assert indices["g_index"] == 3


def test_compute_indices_g_index_borrowing_with_tail_outlier():
    """g-index 'borrowing' edge case Egghe documents: a later highly-cited paper
    can keep the g-core growing even when an interior paper has few citations.
    For [10, 4, 4, 4, 4, 0]: cumulative=10,14,18,22,26 → g=5 (26 >= 25).
    Confirms the early-break is correct for sorted-descending lists (cumulative
    monotonic, i^2 grows quadratically, so once cumulative<i^2 it stays below)."""
    from app.analysis.authors import _compute_indices
    indices = _compute_indices([10, 4, 4, 4, 4, 0], pub_count=6)
    assert indices["h_index"] == 4  # [10,4,4,4] all >= 4; 5th is 4 not >=5
    assert indices["g_index"] == 5  # cumsum at top-5 is 26 >= 25


def test_compute_indices_zero_citations():
    from app.analysis.authors import _compute_indices
    indices = _compute_indices([0, 0, 0], pub_count=3)
    assert indices == {"h_index": 0, "g_index": 0, "e_index": 0.0}


def test_compute_indices_empty():
    from app.analysis.authors import _compute_indices
    indices = _compute_indices([], pub_count=0)
    assert indices == {"h_index": 0, "g_index": 0, "e_index": 0.0}


def test_author_top_includes_h_index(db):
    project = SearchProject(name="HI")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="t")
    db.add(query)
    db.flush()
    a = Author(name="Doe, Jane", name_normalized="doe jane")
    pubs = [
        Publication(pmid=f"h{i}", title=f"P{i}", year=2024, citation_count=c, query_id=query.id, project_id=project.id)
        for i, c in enumerate([10, 8, 5, 2, 1])
    ]
    for p in pubs:
        p.authors.append(a)
    db.add_all(pubs)
    db.commit()
    result = analyze_authors(db, project.id)
    top = result["top_authors"][0]
    assert top["name"] == "Doe, Jane"
    # Citations: [10, 8, 5, 2, 1]. Paper 3 has 5 >= 3 → h advances; paper 4 has 2 < 4 → h stops at 3.
    assert top["h_index"] == 3
    # Cumulative top-3 = 23 >= 9; top-4 = 25 >= 16; top-5 = 26 < 25? 26 >= 25 → g=5.
    assert top["g_index"] == 5
    assert top["citation_sum"] == 26
