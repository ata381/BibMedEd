"""Database-level, websocket and startup-configuration guards for read-only mode.

The ORM ``before_flush`` hook alone misses Core statements, ``Query.update``,
raw SQL and bulk helpers, so request sessions run on connections the database
itself holds read-only. Each write path below must fail against that engine.
"""

import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, insert, select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from starlette.websockets import WebSocket, WebSocketDisconnect

import app.read_only as read_only_module
from app.config import settings, unrecognised_env_vars
from app.database import Base
from app.models import SearchProject
from app.read_only import POSTGRES_READ_ONLY_OPTIONS, WEBSOCKET_POLICY_VIOLATION, create_read_only_engine


@pytest.fixture
def demo_db_url():
    # A named shared-cache in-memory database is visible to every engine in the
    # process while at least one connection stays open, with no filesystem use.
    url = f"sqlite:///file:readonly-{uuid.uuid4().hex}?mode=memory&cache=shared&uri=true"
    owner = create_engine(url)
    keepalive = owner.connect()
    Base.metadata.create_all(owner)
    with Session(owner) as session:
        session.add(SearchProject(name="keep"))
        session.commit()
    yield url
    keepalive.close()
    owner.dispose()


@pytest.fixture
def read_only_session(demo_db_url):
    engine = create_read_only_engine(demo_db_url)
    session = Session(engine)
    yield session
    session.close()
    engine.dispose()


def _project_names(url: str) -> list[str]:
    engine = create_engine(url)
    try:
        with Session(engine) as session:
            return list(session.scalars(select(SearchProject.name)))
    finally:
        engine.dispose()


WRITE_PATHS = {
    "orm_add_commit": lambda s: s.add(SearchProject(name="x")),
    "core_insert": lambda s: s.execute(insert(SearchProject).values(name="x")),
    "core_update": lambda s: s.execute(update(SearchProject).values(name="x")),
    "core_delete": lambda s: s.execute(delete(SearchProject)),
    "query_update": lambda s: s.query(SearchProject).update({"name": "x"}),
    "query_delete": lambda s: s.query(SearchProject).delete(),
    "raw_text_update": lambda s: s.execute(text("UPDATE search_projects SET name = 'x'")),
    "raw_text_ddl": lambda s: s.execute(text("CREATE TABLE evil (id INTEGER)")),
    "bulk_insert_mappings": lambda s: s.bulk_insert_mappings(SearchProject, [{"name": "x"}]),
}


@pytest.mark.parametrize("write", WRITE_PATHS.values(), ids=WRITE_PATHS.keys())
def test_read_only_engine_rejects_every_write_path(read_only_session, demo_db_url, write):
    with pytest.raises(OperationalError, match="readonly"):
        write(read_only_session)
        read_only_session.commit()
    read_only_session.rollback()

    assert _project_names(demo_db_url) == ["keep"]


def test_read_only_engine_still_serves_reads(read_only_session):
    assert list(read_only_session.scalars(select(SearchProject.name))) == ["keep"]


def test_get_db_uses_read_only_engine_in_read_only_mode(monkeypatch, demo_db_url):
    from app.database import get_db

    monkeypatch.setattr(settings, "read_only", True)
    monkeypatch.setattr(settings, "database_url", demo_db_url)
    monkeypatch.setattr("app.database._ReadOnlySessionLocal", None)
    generator = get_db()
    session = next(generator)
    try:
        with pytest.raises(OperationalError):
            session.execute(text("DELETE FROM search_projects"))
    finally:
        generator.close()
        session.get_bind().dispose()

    assert _project_names(demo_db_url) == ["keep"]


def test_postgres_engine_uses_read_only_default_transactions(monkeypatch):
    captured = {}

    def fake_create_engine(url, **kwargs):
        captured.update(url=url, **kwargs)
        return object()

    monkeypatch.setattr(read_only_module, "create_engine", fake_create_engine)

    create_read_only_engine("postgresql://u:p@db/bibmeded")

    assert captured["connect_args"] == {"options": POSTGRES_READ_ONLY_OPTIONS}


def test_unsupported_database_fails_loudly():
    with pytest.raises(RuntimeError, match="mysql"):
        create_read_only_engine("mysql://u:p@db/bibmeded")


def _app_with_websocket(db, read_only: bool, monkeypatch):
    from app.database import get_db
    from app.main import create_app

    monkeypatch.setattr(settings, "read_only", read_only)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db

    @app.websocket("/ws/test")
    async def echo(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("hello")
        await websocket.close()

    return app


def test_websockets_are_closed_in_read_only_mode(db, monkeypatch):
    client = TestClient(_app_with_websocket(db, read_only=True, monkeypatch=monkeypatch))

    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("/ws/test"):
            pass

    assert excinfo.value.code == WEBSOCKET_POLICY_VIOLATION


def test_websockets_work_in_default_mode(db, monkeypatch):
    client = TestClient(_app_with_websocket(db, read_only=False, monkeypatch=monkeypatch))

    with client.websocket_connect("/ws/test") as websocket:
        assert websocket.receive_text() == "hello"


def test_unrecognised_env_vars_flags_typos_only():
    environ = {
        "BIBMEDED_READ_ONLY": "true",
        "BIBMEDED_DATABASE_URL": "sqlite://",
        "BIBMEDED_LOG_LEVEL": "DEBUG",
        "bibmeded_lens_api_key": "x",
        "BIBMEDED_READONLY": "true",
        "BIBMEDED_PUBMED_KEY": "x",
        "PATH": "/usr/bin",
    }

    assert unrecognised_env_vars(environ) == ["BIBMEDED_PUBMED_KEY", "BIBMEDED_READONLY"]


@pytest.mark.parametrize("read_only", [True, False])
def test_startup_logs_mode_and_warns_on_unknown_env_vars(db, monkeypatch, caplog, read_only):
    from app.database import get_db
    from app.main import create_app

    monkeypatch.setattr("app.main._seed_read_only_demo", lambda: None)
    monkeypatch.setattr(settings, "read_only", read_only)
    monkeypatch.setenv("BIBMEDED_READONLY", "true")
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    caplog.set_level(logging.INFO, logger="app.main")

    with TestClient(app):
        pass

    messages = [record.getMessage() for record in caplog.records if record.name == "app.main"]
    assert f"BibMedEd mode: read_only={read_only}" in messages
    assert any("BIBMEDED_READONLY" in m and "unrecognised" in m for m in messages)
