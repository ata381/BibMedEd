"""Database-level, websocket and startup-configuration guards for read-only mode.

The ORM ``before_flush`` hook alone misses Core statements, ``Query.update``,
raw SQL and bulk helpers, so request sessions run on connections the database
itself holds read-only. Each write path below must fail against that engine.
"""

import logging
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, insert, make_url, select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from starlette.websockets import WebSocket, WebSocketDisconnect

import bibmeded.read_only as read_only_module
from bibmeded.config import settings, unrecognised_env_vars
from bibmeded.database import Base
from bibmeded.models import SearchProject
from bibmeded.read_only import (
    POSTGRES_READ_ONLY_OPTIONS,
    REASSERT_STATEMENTS,
    WEBSOCKET_POLICY_VIOLATION,
    create_read_only_engine,
    verify_read_only_engine,
)


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
    from bibmeded.database import get_db

    monkeypatch.setattr(settings, "read_only", True)
    monkeypatch.setattr(settings, "database_url", demo_db_url)
    monkeypatch.setattr("bibmeded.database._ReadOnlySessionLocal", None)
    generator = get_db()
    session = next(generator)
    try:
        with pytest.raises(OperationalError):
            session.execute(text("DELETE FROM search_projects"))
    finally:
        generator.close()
        session.get_bind().dispose()

    assert _project_names(demo_db_url) == ["keep"]


def _capture_postgres_engine(monkeypatch, url: str) -> dict:
    captured = {}

    def fake_create_engine(engine_url, **kwargs):
        captured.update(url=engine_url, **kwargs)
        return MagicMock()

    monkeypatch.setattr(read_only_module, "create_engine", fake_create_engine)
    monkeypatch.setattr(read_only_module.event, "listen", MagicMock())
    create_read_only_engine(url)
    return captured


@pytest.mark.parametrize(
    "url",
    ["postgresql://u:p@db/bibmeded", "postgresql+psycopg2://u:p@db/bibmeded", "postgresql+psycopg://u:p@db/bibmeded"],
)
def test_postgres_engine_uses_read_only_default_transactions(monkeypatch, url):
    captured = _capture_postgres_engine(monkeypatch, url)

    assert captured["connect_args"] == {"options": POSTGRES_READ_ONLY_OPTIONS}
    assert captured["url"].drivername == url.split(":")[0]


def test_postgres_engine_merges_existing_options(monkeypatch):
    captured = _capture_postgres_engine(
        monkeypatch,
        "postgresql+psycopg2://u:p@db/bibmeded?options=-c%20statement_timeout%3D5000&sslmode=require",
    )

    assert captured["connect_args"] == {"options": f"-c statement_timeout=5000 {POSTGRES_READ_ONLY_OPTIONS}"}
    assert "options" not in captured["url"].query
    assert captured["url"].query["sslmode"] == "require"


def test_postgres_engine_reasserts_read_only_on_checkout(monkeypatch):
    _capture_postgres_engine(monkeypatch, "postgresql+psycopg2://u:p@db/bibmeded")

    (engine, identifier, listener), _ = read_only_module.event.listen.call_args
    assert identifier == "checkout"
    dbapi_connection = MagicMock()
    listener(dbapi_connection, None, None)
    dbapi_connection.cursor.return_value.execute.assert_called_once_with(REASSERT_STATEMENTS["postgresql"])
    dbapi_connection.commit.assert_called_once()


def test_lifted_sqlite_guard_does_not_survive_pool_checkin(read_only_session, demo_db_url):
    engine = read_only_session.get_bind()
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA query_only = OFF")
        assert connection.exec_driver_sql("PRAGMA query_only").scalar() == 0

    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA query_only").scalar() == 1
        with pytest.raises(OperationalError, match="readonly"):
            connection.exec_driver_sql("DELETE FROM search_projects")

    assert _project_names(demo_db_url) == ["keep"]


def test_verify_accepts_guarded_sqlite_engine(read_only_session):
    verify_read_only_engine(read_only_session.get_bind())


def test_verify_rejects_unguarded_sqlite_engine(demo_db_url):
    engine = create_engine(demo_db_url)
    try:
        with pytest.raises(RuntimeError, match="not active"):
            verify_read_only_engine(engine)
    finally:
        engine.dispose()


@pytest.mark.parametrize("reported, ok", [("on", True), ("off", False)])
def test_verify_checks_postgres_transaction_read_only(reported, ok):
    engine = MagicMock()
    engine.url = make_url("postgresql+psycopg2://u:p@db/bibmeded")
    connection = engine.connect.return_value.__enter__.return_value
    connection.exec_driver_sql.return_value.scalar.return_value = reported

    if ok:
        verify_read_only_engine(engine)
    else:
        with pytest.raises(RuntimeError, match="not active"):
            verify_read_only_engine(engine)
    connection.exec_driver_sql.assert_called_once_with("SHOW transaction_read_only")


def test_startup_verification_uses_the_read_only_engine(monkeypatch, demo_db_url):
    from bibmeded.main import _verify_read_only_guard

    monkeypatch.setattr(settings, "database_url", demo_db_url)
    monkeypatch.setattr("bibmeded.database._ReadOnlySessionLocal", None)
    try:
        _verify_read_only_guard()
    finally:
        from bibmeded.database import get_read_only_engine

        get_read_only_engine().dispose()


def test_unsupported_database_fails_loudly():
    with pytest.raises(RuntimeError, match="mysql"):
        create_read_only_engine("mysql://u:p@db/bibmeded")


def _app_with_websocket(db, read_only: bool, monkeypatch):
    from bibmeded.database import get_db
    from bibmeded.main import create_app

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
    from bibmeded.database import get_db
    from bibmeded.main import create_app

    monkeypatch.setattr("bibmeded.main._seed_read_only_demo", lambda: None)
    monkeypatch.setattr("bibmeded.main._verify_read_only_guard", lambda: None)
    monkeypatch.setattr(settings, "read_only", read_only)
    monkeypatch.setenv("BIBMEDED_READONLY", "true")
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    caplog.set_level(logging.INFO, logger="bibmeded.main")

    with TestClient(app):
        pass

    messages = [record.getMessage() for record in caplog.records if record.name == "bibmeded.main"]
    assert f"BibMedEd mode: read_only={read_only}" in messages
    assert any("BIBMEDED_READONLY" in m and "unrecognised" in m for m in messages)


def test_postgres_driver_validator_survives_alongside_read_only_settings():
    from bibmeded.config import Settings

    configured = Settings(_env_file=None, database_url="postgres://u:p@h/db", read_only=True)

    assert configured.database_url == "postgresql+psycopg2://u:p@h/db"
    assert configured.read_only is True
    assert "_pin_postgres_driver" in Settings.__pydantic_decorators__.field_validators


@pytest.mark.parametrize("raw", ["postgres://u:p@h/db", "postgresql://u:p@h/db", "postgresql+psycopg2://u:p@h/db"])
def test_read_only_engine_accepts_the_normalised_psycopg2_url(raw):
    from bibmeded.config import Settings

    normalised = Settings(_env_file=None, database_url=raw).database_url
    engine = create_read_only_engine(normalised)
    try:
        assert engine.url.drivername == "postgresql+psycopg2"
        assert engine.dialect.driver == "psycopg2"
    finally:
        engine.dispose()


@pytest.mark.parametrize("url", ["sqlite://", "sqlite:///:memory:"])
def test_read_only_engine_rejects_private_in_memory_sqlite(url):
    with pytest.raises(RuntimeError, match="in-memory"):
        create_read_only_engine(url)


def test_compose_forwards_read_only_flag_to_api():
    compose = (Path(__file__).resolve().parents[1] / "docker-compose.yml").read_text(encoding="utf-8")
    api_block = compose.split("\n  api:\n", 1)[1].split("\n  worker:\n", 1)[0]
    assert "BIBMEDED_READ_ONLY: ${BIBMEDED_READ_ONLY:-false}" in api_block
