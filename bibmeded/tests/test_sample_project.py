from bibmeded.config import settings
from bibmeded.models import QueryStatus, SearchProject, SearchQuery
from bibmeded.services.sample_project import (
    LEGACY_SAMPLE_QUERY_STRING,
    SAMPLE_QUERY_STRING,
    get_or_create_sample_project,
)


def _legacy_sample_project(db) -> SearchProject:
    project, _ = get_or_create_sample_project(db)
    db.query(SearchQuery).filter(SearchQuery.project_id == project.id).update(
        {SearchQuery.query_string: LEGACY_SAMPLE_QUERY_STRING}
    )
    db.commit()
    return project


def _query_strings(db, project_id: int) -> list[str]:
    return [
        query_string
        for (query_string,) in db.query(SearchQuery.query_string)
        .filter(SearchQuery.project_id == project_id)
        .order_by(SearchQuery.id)
    ]


def test_reusing_a_legacy_sample_project_replaces_the_placeholder_query(db):
    project = _legacy_sample_project(db)

    reused, created = get_or_create_sample_project(db)

    assert created is False
    assert reused.id == project.id
    assert _query_strings(db, project.id) == [SAMPLE_QUERY_STRING]


def test_reusing_a_sample_project_keeps_searches_the_user_ran_in_it(db):
    project = _legacy_sample_project(db)
    project_id = project.id
    db.add_all(
        [
            SearchQuery(
                project_id=project_id,
                query_string=LEGACY_SAMPLE_QUERY_STRING,
                database="pubmed",
                status=QueryStatus.completed,
            ),
            SearchQuery(
                project_id=project_id,
                query_string='"clinical reasoning"[tiab]',
                database="sample",
                status=QueryStatus.completed,
            ),
        ]
    )
    db.commit()

    get_or_create_sample_project(db)

    assert _query_strings(db, project_id) == [
        SAMPLE_QUERY_STRING,
        LEGACY_SAMPLE_QUERY_STRING,
        '"clinical reasoning"[tiab]',
    ]


def test_reusing_a_legacy_sample_project_writes_nothing_in_read_only_mode(db, monkeypatch):
    project = _legacy_sample_project(db)
    project_id = project.id
    monkeypatch.setattr(settings, "read_only", True)

    reused, created = get_or_create_sample_project(db)

    assert created is False
    assert reused.id == project_id
    assert _query_strings(db, project_id) == [LEGACY_SAMPLE_QUERY_STRING]
