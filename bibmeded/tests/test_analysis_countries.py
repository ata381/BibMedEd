from app.models import Affiliation, Author, Publication, SearchProject, SearchQuery
from app.analysis.countries import analyze_countries


def test_country_analysis(db):
    project = SearchProject(name="Test")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="test")
    db.add(query)
    db.flush()

    aff_us = Affiliation(name="Harvard University", country="United States", name_normalized="harvard university")
    aff_uk = Affiliation(name="University of Oxford", country="United Kingdom", name_normalized="university of oxford")
    aff_de = Affiliation(name="Charite Berlin", country="Germany", name_normalized="charite berlin")

    a1 = Author(name="Smith, John", name_normalized="smith john c")
    a1.affiliations.append(aff_us)
    a2 = Author(name="Jones, Alice", name_normalized="jones alice c")
    a2.affiliations.append(aff_uk)
    a3 = Author(name="Mueller, Hans", name_normalized="mueller hans c")
    a3.affiliations.append(aff_de)

    pub1 = Publication(pmid="country1", title="Paper 1", year=2024, query_id=query.id)
    pub1.authors.extend([a1, a2])
    pub2 = Publication(pmid="country2", title="Paper 2", year=2024, query_id=query.id)
    pub2.authors.extend([a1, a3])
    db.add_all([pub1, pub2])
    db.commit()

    result = analyze_countries(db, project.id)
    assert len(result["country_counts"]) == 3
    country_names = [c["country"] for c in result["country_counts"]]
    assert "United States" in country_names
    assert "United Kingdom" in country_names
    assert "Germany" in country_names
    # US appears in both papers, so it should have the highest count
    us_entry = next(c for c in result["country_counts"] if c["country"] == "United States")
    assert us_entry["count"] == 2
    assert len(result["institution_counts"]) == 3
    # Collaboration network should have links between co-occurring countries
    assert len(result["collaboration_network"]["nodes"]) == 3
    assert len(result["collaboration_network"]["links"]) >= 2


def test_country_analysis_empty(db):
    project = SearchProject(name="Empty")
    db.add(project)
    db.commit()
    result = analyze_countries(db, project.id)
    assert result["country_counts"] == []
    assert result["institution_counts"] == []
    assert result["collaboration_network"]["nodes"] == []


def test_country_analysis_nonexistent_project(db):
    result = analyze_countries(db, 99999)
    assert result["country_counts"] == []
