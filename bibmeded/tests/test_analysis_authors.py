import math

import pytest

from bibmeded.models import Author, Publication, SearchProject, SearchQuery
from bibmeded.analysis.authors import analyze_author_productivity, analyze_authors
from bibmeded.analysis.lotka import fit_lotka

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
    from bibmeded.analysis.authors import _compute_indices
    indices = _compute_indices([5, 4, 3, 2, 1], pub_count=5)
    assert indices["h_index"] == 3
    assert indices["g_index"] == 3
    assert indices["e_index"] == 1.73


def test_compute_indices_g_index_rewards_outliers():
    """g-index promotes one highly-cited paper. [20,1,1] → h=1 but g=3 (1*20+1+1=22 >= 9)."""
    from bibmeded.analysis.authors import _compute_indices
    indices = _compute_indices([20, 1, 1], pub_count=3)
    assert indices["h_index"] == 1
    assert indices["g_index"] == 3


def test_compute_indices_g_index_borrowing_with_tail_outlier():
    """g-index 'borrowing' edge case Egghe documents: a later highly-cited paper
    can keep the g-core growing even when an interior paper has few citations.
    For [10, 4, 4, 4, 4, 0]: cumulative=10,14,18,22,26 → g=5 (26 >= 25).
    Confirms the early-break is correct for sorted-descending lists (cumulative
    monotonic, i^2 grows quadratically, so once cumulative<i^2 it stays below)."""
    from bibmeded.analysis.authors import _compute_indices
    indices = _compute_indices([10, 4, 4, 4, 4, 0], pub_count=6)
    assert indices["h_index"] == 4  # [10,4,4,4] all >= 4; 5th is 4 not >=5
    assert indices["g_index"] == 5  # cumsum at top-5 is 26 >= 25


def test_compute_indices_zero_citations():
    from bibmeded.analysis.authors import _compute_indices
    indices = _compute_indices([0, 0, 0], pub_count=3)
    assert indices == {"h_index": 0, "g_index": 0, "e_index": 0.0}


def test_compute_indices_empty():
    from bibmeded.analysis.authors import _compute_indices
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


def _counts(distribution: dict[int, int]) -> list[int]:
    """Per-author paper counts for a {papers: number_of_authors} distribution."""
    return [papers for papers, authors in distribution.items() for _ in range(authors)]


# 3600 / n^2 is an exact inverse-square law, so the log-log fit is exact.
INVERSE_SQUARE = {1: 3600, 2: 900, 3: 400, 4: 225, 5: 144, 6: 100}


def test_lotka_fits_an_exact_inverse_square_law():
    lotka = fit_lotka(_counts(INVERSE_SQUARE))
    assert lotka["distribution"] == [{"papers": n, "authors": a} for n, a in INVERSE_SQUARE.items()]
    assert lotka["total_authors"] == 5369
    assert lotka["productivity_levels"] == 6
    assert lotka["reason"] is None
    fit = lotka["fit"]
    assert fit["alpha"] == 2.0
    assert fit["C"] == 3600.0
    assert fit["r_squared"] == 1.0


def test_lotka_ks_rejects_a_distribution_truncated_at_six_papers():
    """Pao (1985) compares against the infinite Lotka distribution with C = 1/zeta(alpha).
    For alpha = 2 that is 6/pi^2 = 0.6079. The data stop at 6 papers, so the observed
    cumulative share reaches 1 while the expected one is 0.6079 * sum(1/n^2, n<=6) = 0.9067:
    D = 0.0933, above the 0.01-level critical value 1.63 / sqrt(5369) = 0.0222."""
    gof = fit_lotka(_counts(INVERSE_SQUARE))["fit"]["goodness_of_fit"]
    assert gof["test"] == "kolmogorov-smirnov"
    assert gof["significance_level"] == 0.01
    assert gof["expected_single_paper_share"] == pytest.approx(6 / math.pi**2, abs=1e-4)
    assert gof["D"] == pytest.approx(0.0933, abs=1e-4)
    assert gof["critical_value"] == pytest.approx(0.0222, abs=1e-4)
    assert gof["consistent_with_lotka"] is False
    assert gof["reason"] is None


def test_lotka_ks_accepts_a_sample_close_to_the_inverse_square_law():
    """About 100 * 0.6079 / n^2 authors per level, rounded, up to 10 papers."""
    distribution = {1: 61, 2: 15, 3: 7, 4: 4, 5: 2, 6: 2, 7: 1, 8: 1, 9: 1, 10: 1}
    lotka = fit_lotka(_counts(distribution))
    fit = lotka["fit"]
    assert lotka["total_authors"] == 95
    assert 1.8 < fit["alpha"] < 2.0
    assert fit["goodness_of_fit"]["D"] < fit["goodness_of_fit"]["critical_value"]
    assert fit["goodness_of_fit"]["consistent_with_lotka"] is True


def test_lotka_fit_uses_every_level_including_a_sparse_tail():
    """No tail cutoff is applied: single authors at 12-50 papers enter the fit with the
    same weight as the 61 single-paper authors and pull alpha towards 1. Documented in
    docs/scripting.md so a reader is not surprised by it."""
    head = {1: 61, 2: 15, 3: 7, 4: 4, 5: 2, 6: 2, 7: 1, 8: 1, 9: 1, 10: 1}
    with_tail = {**head, 12: 1, 15: 1, 20: 1, 30: 1, 50: 1}
    assert fit_lotka(_counts(with_tail))["fit"]["alpha"] < fit_lotka(_counts(head))["fit"]["alpha"] - 0.5


def test_lotka_needs_three_productivity_levels():
    """Two points always fit a line exactly (R^2 = 1), so an exponent from them says nothing."""
    lotka = fit_lotka(_counts({1: 10, 2: 3}))
    assert lotka["fit"] is None
    assert "3 distinct" in lotka["reason"]
    assert lotka["distribution"] == [{"papers": 1, "authors": 10}, {"papers": 2, "authors": 3}]
    assert lotka["total_authors"] == 13


def test_lotka_without_authors_explains_the_missing_fit():
    lotka = fit_lotka([])
    assert lotka["distribution"] == []
    assert lotka["total_authors"] == 0
    assert lotka["fit"] is None
    assert lotka["reason"]


def test_lotka_refuses_a_flat_distribution():
    """One author at every level gives log(authors) no variance, so R^2 is undefined."""
    lotka = fit_lotka([1, 2, 3, 4])
    assert lotka["fit"] is None
    assert "same number of authors" in lotka["reason"]


def test_lotka_skips_the_ks_verdict_for_small_samples():
    """1.63 / sqrt(N) is the asymptotic 0.01 critical value, only valid above 35 authors."""
    gof = fit_lotka(_counts({1: 20, 2: 5, 3: 2, 4: 1}))["fit"]["goodness_of_fit"]
    assert gof["D"] is not None
    assert gof["critical_value"] is None
    assert gof["consistent_with_lotka"] is None
    assert "35" in gof["reason"]


def test_lotka_skips_the_ks_test_when_alpha_is_not_above_one():
    """The Lotka distribution only normalises (sum of 1/n^alpha converges) for alpha > 1."""
    fit = fit_lotka(_counts({1: 5, 2: 6, 3: 8, 4: 9}))["fit"]
    assert fit["alpha"] < 1
    gof = fit["goodness_of_fit"]
    assert gof["D"] is None
    assert gof["critical_value"] is None
    assert gof["consistent_with_lotka"] is None
    assert gof["expected_single_paper_share"] is None
    assert "alpha" in gof["reason"]


def test_lotka_gates_the_ks_test_when_alpha_rounds_to_one():
    """Floating-point error can leave the slope a hair above 1 where it is exactly 1 in
    exact arithmetic; the gate must agree with the alpha the caller sees."""
    fit = fit_lotka(_counts({1: 12, 2: 27, 3: 3}))["fit"]
    assert fit["alpha"] == 1.0
    gof = fit["goodness_of_fit"]
    assert gof["D"] is None
    assert gof["expected_single_paper_share"] is None
    assert "alpha" in gof["reason"]


def test_lotka_rejects_non_positive_paper_counts():
    with pytest.raises(ValueError):
        fit_lotka([1, 0, 2])


def test_lotka_names_its_method_and_sources():
    method = fit_lotka([])["method"]
    assert "Lotka 1926" in method
    assert "Pao 1985" in method


def _seed_productivity_corpus(db):
    """Ames, Bell and Cole have 1 included paper, Dunn 2, Eyre 3. Fox's only paper is
    excluded, so Fox must not be counted. Eyre also has an excluded fourth paper, which
    must not raise her count to 4."""
    project = SearchProject(name="Lotka")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="t")
    db.add(query)
    db.flush()
    authors = {n: Author(name=n, name_normalized=n.lower()) for n in ["Ames", "Bell", "Cole", "Dunn", "Eyre", "Fox"]}
    for i, names in enumerate([("Ames", "Eyre"), ("Bell", "Eyre"), ("Cole", "Dunn"), ("Dunn", "Eyre")]):
        pub = Publication(pmid=f"lk{i}", title=f"L{i}", year=2024, citation_count=1, query_id=query.id, project_id=project.id)
        pub.authors.extend(authors[n] for n in names)
        db.add(pub)
    excluded = Publication(pmid="lkx", title="LX", year=2024, query_id=query.id, project_id=project.id,
                           excluded=True, exclusion_reason="other", screening_stage="title_abstract")
    excluded.authors.append(authors["Fox"])
    db.add(excluded)
    excluded_for_eyre = Publication(pmid="lky", title="LY", year=2024, query_id=query.id, project_id=project.id,
                                    excluded=True, exclusion_reason="other", screening_stage="full_text")
    excluded_for_eyre.authors.append(authors["Eyre"])
    db.add(excluded_for_eyre)
    db.commit()
    return project


def test_author_analysis_includes_lotka_reconciled_with_total_authors(db):
    project = _seed_productivity_corpus(db)
    result = analyze_authors(db, project.id)
    lotka = result["lotka"]
    assert lotka["distribution"] == [
        {"papers": 1, "authors": 3}, {"papers": 2, "authors": 1}, {"papers": 3, "authors": 1},
    ]
    assert lotka["total_authors"] == result["total_authors"] == 5
    assert sum(level["authors"] for level in lotka["distribution"]) == result["total_authors"]
    eyre = next(a for a in result["top_authors"] if a["name"] == "Eyre")
    assert eyre["pub_count"] == 3


def test_author_productivity_query_matches_the_authors_analysis(db):
    project = _seed_productivity_corpus(db)
    productivity = analyze_author_productivity(db, project.id)
    assert productivity["distribution"] == [
        {"papers": 1, "authors": 3}, {"papers": 2, "authors": 1}, {"papers": 3, "authors": 1},
    ]
    assert productivity["total_authors"] == 5
    assert productivity == analyze_authors(db, project.id)["lotka"]


def test_author_analysis_empty_project_still_reports_lotka(db):
    project = SearchProject(name="Empty Lotka")
    db.add(project)
    db.commit()
    assert analyze_authors(db, project.id)["lotka"]["fit"] is None
    assert analyze_author_productivity(db, project.id)["total_authors"] == 0
    assert analyze_author_productivity(db, 999999)["total_authors"] == 0
