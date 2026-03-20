from datetime import date
from app.models import Author, Journal, Keyword, KeywordType, Publication, SearchProject, SearchQuery


def test_create_project(db):
    project = SearchProject(name="AI in Medical Education", date_range_start=date(2022, 1, 1), date_range_end=date(2025, 6, 30))
    db.add(project)
    db.flush()
    assert project.id is not None
    assert project.name == "AI in Medical Education"


def test_create_publication_with_author(db):
    journal = Journal(name="JMIR Medical Education", issn="2369-3762")
    db.add(journal)
    db.flush()
    pub = Publication(pmid="12345678", title="Test Article", year=2024, journal=journal)
    author = Author(name="Smith, John", name_normalized="smith john")
    pub.authors.append(author)
    db.add(pub)
    db.flush()
    assert pub.id is not None
    assert len(pub.authors) == 1
    assert pub.journal.name == "JMIR Medical Education"


def test_create_keyword(db):
    kw = Keyword(term="Artificial Intelligence", type=KeywordType.mesh_term, term_normalized="artificial intelligence")
    db.add(kw)
    db.flush()
    assert kw.id is not None


def test_project_query_relationship(db):
    project = SearchProject(name="Test Project")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string='"artificial intelligence" AND "medical education"')
    db.add(query)
    db.flush()
    assert len(project.queries) == 1
    assert project.queries[0].query_string == query.query_string
