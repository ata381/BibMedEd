"""BIBMEDED_READ_ONLY public-demo mode.

The demo is only safe to expose publicly if no request can mutate the database
or trigger an outbound API call, so these tests enumerate every registered route
rather than relying on a hand-maintained list.
"""

import re
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from bibmeded.analysis import ANALYSIS_FUNCTIONS
from bibmeded.config import Settings, settings
from bibmeded.models import AnalysisRun, Publication, QueryStatus, SearchProject, SearchQuery
from bibmeded.read_only import (
    READ_ONLY_DETAIL,
    SAFE_METHODS,
    ReadOnlyViolation,
    _reject_flush,
    guard_session,
)
from bibmeded.services.demo_seed import seed_demo_data
from bibmeded.services.sample_project import SAMPLE_PROJECT_KEY

EXPECTED_BLOCKED_ROUTES = {
    ("POST", "/api/projects"),
    ("POST", "/api/projects/sample"),
    ("PATCH", "/api/projects/{project_id}"),
    ("DELETE", "/api/projects/{project_id}"),
    ("POST", "/api/projects/{project_id}/search"),
    ("POST", "/api/projects/{project_id}/publications/bulk-exclude"),
    ("PATCH", "/api/projects/{project_id}/publications/{publication_id}/exclude"),
    ("POST", "/api/projects/{project_id}/analysis/{analysis_type}"),
}
EXPORT_FORMATS = ("csv", "ris", "bibtex", "json", "prisma", "methodology", "bundle")


def _build_app(db, read_only: bool, monkeypatch):
    from bibmeded.database import get_db
    from bibmeded.main import create_app

    monkeypatch.setattr(settings, "read_only", read_only)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return app


def _mutating_routes(app) -> list[tuple[str, str]]:
    # Enumerated from the OpenAPI schema because newer FastAPI versions wrap
    # included routers, hiding their APIRoutes from ``app.routes``.
    return sorted(
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if method.upper() not in SAFE_METHODS
    )


def _concrete_path(path: str, project_id: int, publication_id: int) -> str:
    values = {"project_id": project_id, "publication_id": publication_id, "analysis_type": "publications"}
    return re.sub(r"\{(\w+)\}", lambda m: str(values[m.group(1)]), path)


def _row_counts(db) -> dict[str, int]:
    return {
        model.__name__: db.scalar(select(func.count()).select_from(model))
        for model in (SearchProject, SearchQuery, Publication, AnalysisRun)
    }


@pytest.fixture
def demo_project(db):
    return seed_demo_data(db)


@pytest.fixture
def read_only_client(db, demo_project, monkeypatch):
    guard_session(db)
    app = _build_app(db, read_only=True, monkeypatch=monkeypatch)
    return TestClient(app)


@pytest.fixture
def default_client(db, monkeypatch):
    return TestClient(_build_app(db, read_only=False, monkeypatch=monkeypatch))


def test_read_only_defaults_to_false():
    assert Settings(_env_file=None).read_only is False


def test_read_only_reads_environment(monkeypatch):
    monkeypatch.setenv("BIBMEDED_READ_ONLY", "true")
    assert Settings(_env_file=None).read_only is True


def test_route_inventory_matches_audited_mutating_routes(db, monkeypatch):
    app = _build_app(db, read_only=True, monkeypatch=monkeypatch)
    assert set(_mutating_routes(app)) == EXPECTED_BLOCKED_ROUTES


def test_every_mutating_route_returns_403(read_only_client, db, demo_project):
    publication_id = db.scalar(
        select(Publication.id).where(Publication.project_id == demo_project.id).limit(1)
    )
    before = _row_counts(db)
    routes = _mutating_routes(read_only_client.app)
    assert routes

    with patch("bibmeded.routers.search.run_search") as run_search:
        for method, path in routes:
            url = _concrete_path(path, demo_project.id, publication_id)
            response = read_only_client.request(
                method,
                url,
                json={"name": "x", "query_string": "x", "citation_threshold": 999, "reason": "other"},
            )
            assert response.status_code == 403, (method, url, response.text)
            assert response.json() == {"detail": READ_ONLY_DETAIL, "read_only": True}

    run_search.delay.assert_not_called()
    assert _row_counts(db) == before
    db.refresh(demo_project)
    assert demo_project.name
    assert db.scalar(
        select(func.count()).select_from(Publication).where(Publication.excluded.is_(True))
    ) == 1


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_unregistered_paths_are_blocked_before_routing(read_only_client, method):
    response = read_only_client.request(method, "/api/some-future-endpoint")
    assert response.status_code == 403
    assert response.json()["read_only"] is True


def test_blocked_response_still_carries_cors_headers(read_only_client):
    response = read_only_client.post("/api/projects", json={"name": "x"}, headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 403
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_preflight_is_not_blocked(read_only_client):
    response = read_only_client.options(
        "/api/projects",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert response.status_code == 200


def test_head_request_passes_through_to_routing(read_only_client):
    assert read_only_client.head("/openapi.json").status_code == 200


def test_config_endpoint_reports_read_only(read_only_client):
    assert read_only_client.get("/api/config").json() == {"read_only": True}


def test_config_endpoint_reports_default_mode(default_client):
    assert default_client.get("/api/config").json() == {"read_only": False}


def test_reads_work_in_read_only_mode(read_only_client, demo_project):
    pid = demo_project.id
    projects = read_only_client.get("/api/projects")
    assert projects.status_code == 200
    assert [p["id"] for p in projects.json()] == [pid]

    assert read_only_client.get(f"/api/projects/{pid}").status_code == 200
    publications = read_only_client.get(f"/api/projects/{pid}/publications")
    assert publications.status_code == 200
    assert publications.json()["total"] == 12
    assert read_only_client.get(f"/api/projects/{pid}/search/latest").json()["status"] == "completed"
    assert read_only_client.get("/api/adapters").status_code == 200
    assert read_only_client.get("/api/health").status_code == 200
    assert read_only_client.get("/openapi.json").status_code == 200


@pytest.mark.parametrize("analysis_type", sorted(ANALYSIS_FUNCTIONS))
def test_precomputed_analyses_are_readable(read_only_client, demo_project, analysis_type):
    response = read_only_client.get(f"/api/projects/{demo_project.id}/analysis/{analysis_type}")
    assert response.status_code == 200
    assert response.json()["results"]["schema_version"]


@pytest.mark.parametrize("export_format", EXPORT_FORMATS)
def test_exports_work_in_read_only_mode(read_only_client, demo_project, export_format):
    response = read_only_client.get(f"/api/projects/{demo_project.id}/export/{export_format}")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert response.content


def test_readiness_skips_redis_in_read_only_mode(read_only_client):
    with patch("redis.from_url") as from_url:
        response = read_only_client.get("/api/ready")
    from_url.assert_not_called()
    assert response.status_code == 200
    assert response.json()["checks"] == {"db": "ok", "redis": "skipped"}


def _stale_running_query(db, project_id: int) -> SearchQuery:
    query = SearchQuery(
        project_id=project_id,
        query_string="stale",
        database="pubmed",
        status=QueryStatus.running,
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db.add(query)
    db.commit()
    db.refresh(query)
    return query


def test_stale_search_status_is_reported_but_not_persisted_in_read_only_mode(db, demo_project, monkeypatch):
    query = _stale_running_query(db, demo_project.id)
    guard_session(db)
    client = TestClient(_build_app(db, read_only=True, monkeypatch=monkeypatch))

    response = client.get(f"/api/projects/{demo_project.id}/search/{query.id}")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["progress"] == 0.0
    db.expire_all()
    assert db.get(SearchQuery, query.id).status == QueryStatus.running


def test_stale_search_status_is_persisted_in_default_mode(db, default_client):
    project = SearchProject(name="Stale")
    db.add(project)
    db.commit()
    query = _stale_running_query(db, project.id)

    response = default_client.get(f"/api/projects/{project.id}/search/{query.id}")

    assert response.json()["status"] == "failed"
    db.expire_all()
    assert db.get(SearchQuery, query.id).status == QueryStatus.failed


def test_default_mode_still_allows_mutations(default_client, db):
    created = default_client.post("/api/projects", json={"name": "Writable"})
    assert created.status_code == 201
    pid = created.json()["id"]
    renamed = default_client.patch(f"/api/projects/{pid}", json={"name": "Renamed"})
    assert renamed.json()["name"] == "Renamed"
    deleted = default_client.delete(f"/api/projects/{pid}")
    assert deleted.status_code == 204


def test_guard_session_rejects_flush(db):
    guard_session(db)
    db.add(SearchProject(name="blocked"))
    with pytest.raises(ReadOnlyViolation):
        db.flush()
    db.rollback()


def test_guard_session_is_idempotent(db):
    guard_session(db)
    guard_session(db)
    assert event.contains(db, "before_flush", _reject_flush)
    event.remove(db, "before_flush", _reject_flush)
    assert not event.contains(db, "before_flush", _reject_flush)


def test_get_handler_that_writes_is_mapped_to_403(db, demo_project, monkeypatch):
    guard_session(db)
    app = _build_app(db, read_only=True, monkeypatch=monkeypatch)

    @app.get("/api/test-writes-on-get")
    def writes_on_get():
        db.add(SearchProject(name="sneaky"))
        db.commit()

    response = TestClient(app).get("/api/test-writes-on-get")

    assert response.status_code == 403
    assert response.json()["read_only"] is True


@pytest.mark.parametrize("read_only", [True, False])
def test_get_db_guards_sessions_only_in_read_only_mode(monkeypatch, tmp_path, read_only):
    from bibmeded.database import get_db

    monkeypatch.setattr(settings, "read_only", read_only)
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'guard.db'}")
    monkeypatch.setattr("bibmeded.database._ReadOnlySessionLocal", None)
    generator = get_db()
    session = next(generator)
    try:
        assert event.contains(session, "before_flush", _reject_flush) is read_only
    finally:
        generator.close()


def test_seed_creates_sample_project_and_all_analyses(db):
    project = seed_demo_data(db)

    assert project.sample_key == SAMPLE_PROJECT_KEY
    analysis_types = set(
        db.scalars(select(AnalysisRun.analysis_type).where(AnalysisRun.project_id == project.id))
    )
    assert analysis_types == set(ANALYSIS_FUNCTIONS)


def test_seed_is_idempotent(db):
    first = seed_demo_data(db)
    before = _row_counts(db)

    second = seed_demo_data(db)

    assert second.id == first.id
    assert _row_counts(db) == before


def test_seed_backfills_missing_analyses(db):
    project = seed_demo_data(db)
    db.query(AnalysisRun).filter(
        AnalysisRun.project_id == project.id, AnalysisRun.analysis_type == "keywords"
    ).delete()
    db.commit()

    seed_demo_data(db)

    counts = dict(
        db.execute(
            select(AnalysisRun.analysis_type, func.count())
            .where(AnalysisRun.project_id == project.id)
            .group_by(AnalysisRun.analysis_type)
        ).all()
    )
    assert counts == {name: 1 for name in ANALYSIS_FUNCTIONS}


@pytest.mark.parametrize("read_only, expected_calls", [(True, 1), (False, 0)])
def test_startup_seeds_and_verifies_only_in_read_only_mode(db, monkeypatch, read_only, expected_calls):
    seed = MagicMock()
    verify = MagicMock()
    monkeypatch.setattr("bibmeded.main._seed_read_only_demo", seed)
    monkeypatch.setattr("bibmeded.main._verify_read_only_guard", verify)
    app = _build_app(db, read_only=read_only, monkeypatch=monkeypatch)

    with TestClient(app):
        pass

    assert seed.call_count == expected_calls
    assert verify.call_count == expected_calls


def test_seed_helper_uses_and_closes_its_own_session(monkeypatch):
    import bibmeded.database as database
    from bibmeded.main import _seed_read_only_demo

    session = MagicMock()
    seed = MagicMock()
    monkeypatch.setattr(database, "_engine", object())
    monkeypatch.setattr(database, "_SessionLocal", lambda: session)
    monkeypatch.setattr("bibmeded.services.demo_seed.seed_demo_data", seed)

    _seed_read_only_demo()

    seed.assert_called_once_with(session)
    session.close.assert_called_once()
