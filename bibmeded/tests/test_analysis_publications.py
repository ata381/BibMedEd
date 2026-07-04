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
        db.add(Publication(pmid=f"trend{i}", title=f"P{i}", year=year, query_id=query.id, project_id=project.id))
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
    assert result["field_maturity"] is None


def test_field_maturity_classified_when_enough_years(db):
    project = SearchProject(name="Maturity")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="t")
    db.add(query)
    db.flush()
    # Logistic-shaped accumulation over 8 years — should fit cleanly.
    yearly_totals = [(2017, 2), (2018, 4), (2019, 8), (2020, 14), (2021, 18), (2022, 20), (2023, 21), (2024, 22)]
    pmid_counter = 0
    for year, n in yearly_totals:
        for _ in range(n):
            db.add(Publication(pmid=f"m{pmid_counter}", title=f"P{pmid_counter}", year=year, query_id=query.id, project_id=project.id))
            pmid_counter += 1
    db.commit()
    result = analyze_publication_trends(db, project.id)
    maturity = result["field_maturity"]
    assert maturity is not None
    assert maturity["phase"] in {"emerging", "growing", "mature", "saturating"}
    assert maturity["carrying_capacity"] >= float(result["cumulative"][-1]["cumulative"])
    assert 0.0 <= maturity["fit_quality"] <= 1.0


def test_field_maturity_skipped_when_too_few_years(db):
    project = SearchProject(name="ShortRun")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="t")
    db.add(query)
    db.flush()
    for i, year in enumerate([2023, 2024]):
        db.add(Publication(pmid=f"s{i}", title=f"P{i}", year=year, query_id=query.id, project_id=project.id))
    db.commit()
    result = analyze_publication_trends(db, project.id)
    assert result["field_maturity"] is None


def test_gap_year_does_not_fabricate_single_year_growth_rate(db):
    """3 pubs in 2015, then a 4-year gap (2016-2018 with 0 pubs), then 9 in 2019.

    The true change is spread over 4 calendar years. `growth_rates` must never
    report a fabricated single-year percentage (the old buggy behavior reported
    "200% YoY in 2019" by treating the sparse-list neighbors as adjacent years).
    """
    project = SearchProject(name="GapYear")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="t")
    db.add(query)
    db.flush()
    for i in range(3):
        db.add(Publication(pmid=f"g2015_{i}", title=f"P{i}", year=2015, query_id=query.id, project_id=project.id))
    for i in range(9):
        db.add(Publication(pmid=f"g2019_{i}", title=f"P{i}", year=2019, query_id=query.id, project_id=project.id))
    db.commit()

    result = analyze_publication_trends(db, project.id)

    # yearly_counts must be zero-filled/dense across the gap so the missing
    # years are honestly surfaced, not silently omitted.
    assert result["yearly_counts"] == [
        {"year": 2015, "count": 3},
        {"year": 2016, "count": 0},
        {"year": 2017, "count": 0},
        {"year": 2018, "count": 0},
        {"year": 2019, "count": 9},
    ]
    assert result["total"] == 12

    rates_by_year = {r["year"]: r["rate"] for r in result["growth_rates"]}
    # No entry may report the fabricated 200% single-year spike.
    assert 200.0 not in rates_by_year.values()
    # 2015 -> 2016: real -100% drop to zero.
    assert rates_by_year[2016] == -100.0
    # 2016 -> 2017 and 2017 -> 2018: flat zero-to-zero.
    assert rates_by_year[2017] == 0.0
    assert rates_by_year[2018] == 0.0
    # 2018 -> 2019: growth from a zero base is undefined, not a fabricated
    # percentage.
    assert rates_by_year[2019] is None

    # cumulative must reflect the true year-by-year total, including the gap.
    cumulative_by_year = {c["year"]: c["cumulative"] for c in result["cumulative"]}
    assert cumulative_by_year == {2015: 3, 2016: 3, 2017: 3, 2018: 3, 2019: 12}
