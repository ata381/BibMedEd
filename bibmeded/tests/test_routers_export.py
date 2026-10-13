from datetime import date

from bibmeded.models import Publication, SearchProject, SearchQuery
from bibmeded.models.author import Affiliation, Author, publication_authors


def _project_with_one_publication(db) -> SearchProject:
    project = SearchProject(name="WoS Export")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="q", database="pubmed")
    db.add(query)
    db.flush()
    pub = Publication(
        pmid="31234567",
        doi="10.1111/medu.13900",
        title="Geri bildirim çalışması",
        year=2019,
        source_database="pubmed",
        citation_count=4,
        query_id=query.id,
        project_id=project.id,
        external_references=["10.1000/cited"],
    )
    pub.authors = [
        Author(
            name="Demir, Sofia",
            affiliations=[Affiliation(name="Hacettepe University, Ankara, Turkey", country="Turkey")],
        )
    ]
    excluded = Publication(
        pmid="999",
        title="Excluded record",
        source_database="pubmed",
        query_id=query.id,
        project_id=project.id,
        excluded=True,
        exclusion_reason="other",
        screening_stage="title_abstract",
    )
    db.add_all([pub, excluded])
    db.commit()
    return project


def test_export_wos_returns_utf8_plaintext_attachment(client, db):
    project = _project_with_one_publication(db)

    resp = client.get(f"/api/projects/{project.id}/export/wos")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/plain; charset=utf-8"
    assert resp.headers["content-disposition"] == (
        f'attachment; filename="wos-export-wos-{date.today().isoformat()}.txt"'
    )
    body = resp.content.decode("utf-8")
    assert body.startswith("\ufeffFN Clarivate Analytics Web of Science\nVR 1.0\n")
    assert "TI Geri bildirim çalışması\n" in body
    assert "C1 [Demir, S] Hacettepe University, Ankara, Turkey.\n" in body
    assert "CR DOI 10.1000/cited\n" in body
    assert "Excluded record" not in body
    assert body.endswith("\nEF\n")


def test_export_wos_404_for_unknown_project(client):
    assert client.get("/api/projects/9999/export/wos").status_code == 404


def _project_with_authors_stored_out_of_position_order(db) -> SearchProject:
    project = SearchProject(name="Author Order")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="q", database="pubmed")
    db.add(query)
    db.flush()
    pub = Publication(
        pmid="1", title="Order matters", source_database="pubmed", query_id=query.id, project_id=project.id
    )
    first, second, third = Author(name="Alpha, Ann"), Author(name="Beta, Bob"), Author(name="Gamma, Gil")
    db.add_all([pub, third, second, first])
    db.flush()
    assert first.id > second.id > third.id, "ids must disagree with positions, or the PK order hides the bug"
    for author, position in ((third, 2), (first, 0), (second, 1)):
        db.execute(
            publication_authors.insert().values(
                publication_id=pub.id, author_id=author.id, author_position=position
            )
        )
    db.commit()
    return project


def test_exports_list_authors_in_author_position_order(client, db):
    project = _project_with_authors_stored_out_of_position_order(db)

    wos = client.get(f"/api/projects/{project.id}/export/wos").content.decode("utf-8")
    ris = client.get(f"/api/projects/{project.id}/export/ris").text

    assert "\nAU Alpha, A\n   Beta, B\n   Gamma, G\n" in wos
    assert [line for line in ris.split("\n") if line.startswith("AU  - ")] == [
        "AU  - Alpha, Ann",
        "AU  - Beta, Bob",
        "AU  - Gamma, Gil",
    ]
