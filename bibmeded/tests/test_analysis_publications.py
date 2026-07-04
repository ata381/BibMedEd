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
