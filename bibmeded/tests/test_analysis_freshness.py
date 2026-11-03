import json
import pytest
from bibmeded.models import AnalysisRun, Author, Publication, SearchProject, SearchQuery
from bibmeded.models.author import Affiliation
from bibmeded.models.keyword import Keyword, KeywordType
from bibmeded.models.journal import Journal
from bibmeded.models.citation import Citation


@pytest.mark.parametrize("analysis_type", ["publications", "authors", "countries", "keywords", "citations", "journals"])
def test_analysis_tracks_corpus_changes(client, db, analysis_type):
    project = SearchProject(name="Freshness")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="test")
    db.add(query)
    db.commit()
    url = f"/api/projects/{project.id}/analysis/{analysis_type}"
    empty = client.post(url).json()
    assert empty["stale"] is False
    pub = Publication(pmid="fresh", title="Fresh", year=2024, project_id=project.id, query_id=query.id)
    db.add(pub)
    db.commit()
    assert client.get(url).json()["stale"] is True
    fresh = client.post(url).json()
    assert fresh["results"]["corpus_fingerprint"] != empty["results"]["corpus_fingerprint"]
    assert client.get(url).json()["stale"] is False
    pub.excluded = True
    db.commit()
    assert client.get(url).json()["stale"] is True
    assert client.post(url).json()["stale"] is False
    pub.excluded = False
    db.commit()
    assert client.get(url).json()["stale"] is True


def test_enrichment_and_legacy_analysis(client, db):
    project = SearchProject(name="Enrichment")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="test")
    db.add(query)
    db.flush()
    author = Author(name="A", affiliations=[Affiliation(name="Institute", country="NL")])
    pub = Publication(pmid="enriched", title="Paper", year=2024, project_id=project.id, query_id=query.id,
                      authors=[author], keywords=[Keyword(term="medicine", type=KeywordType.author_keyword)],
                      journal=Journal(name="Journal"))
    db.add(pub)
    db.add(AnalysisRun(project_id=project.id, analysis_type="citations", results=json.dumps({"total_citations": 0})))
    db.commit()
    url = f"/api/projects/{project.id}/analysis/citations"
    assert client.get(url).json()["stale"] is True
    for obj, field, value in [(pub, "citation_count", 3), (pub, "external_references", ["doi:example"]),
                               (author, "name", "Changed"), (author.affiliations[0], "country", "DE"),
                               (pub.keywords[0], "term", "education"), (pub.journal, "name", "New Journal")]:
        client.post(url)
        setattr(obj, field, value)
        db.commit()
        assert client.get(url).json()["stale"] is True, field
    fresh = client.post(url).json()
    text = client.get(f"/api/projects/{project.id}/export/methodology").text
    assert fresh["results"]["corpus_fingerprint"] in text
    db.add(Citation(citing_publication_id=pub.id, cited_publication_id=pub.id))
    db.commit()
    assert client.get(url).json()["stale"] is True


def test_changing_corpus_is_not_cached(client, db, monkeypatch):
    from bibmeded.routers import analysis
    project = SearchProject(name="Concurrent")
    db.add(project)
    db.commit()
    versions = iter(["before", "after"])
    monkeypatch.setattr(analysis, "corpus_fingerprint", lambda *_: next(versions))
    assert client.post(f"/api/projects/{project.id}/analysis/publications").status_code == 409
    assert db.query(AnalysisRun).count() == 0



def test_demo_refreshes_legacy_and_changed_analyses(client, db):
    from bibmeded.services.demo_seed import seed_demo_data
    project = seed_demo_data(db)
    url = f"/api/projects/{project.id}/analysis/publications"
    assert client.get(url).json()["stale"] is False
    run = db.query(AnalysisRun).filter_by(analysis_type="publications").one()
    run.results = json.dumps({"total": 999})
    db.commit()
    seed_demo_data(db)
    assert client.get(url).json()["stale"] is False
    count = db.query(AnalysisRun).count()
    seed_demo_data(db)
    assert db.query(AnalysisRun).count() == count
