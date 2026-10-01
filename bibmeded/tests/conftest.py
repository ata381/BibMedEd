import os

# Set SQLite URL before any app imports to avoid needing psycopg2 during tests.
# pydantic-settings reads env vars when Settings() is instantiated (at config import time),
# so this must be set before bibmeded.config is first imported.
os.environ["BIBMEDED_DATABASE_URL"] = "sqlite://"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    from bibmeded.database import Base
    import bibmeded.models  # noqa: F401 – ensures all models are registered on Base.metadata
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db():
    """Provide a transactional database session that rolls back after each test.

    ``join_transaction_mode="create_savepoint"`` makes the session wrap each of
    its own transactions in a SAVEPOINT, so application-level commit()/rollback()
    never touch the outer transaction that teardown rolls back.

    The SQLAlchemy 1.3-era recipe (a Core ``begin_nested()`` restarted from an
    ``after_transaction_end`` listener) must not come back: that listener also
    fires for every application ``Session.begin_nested()``, stacks stray Core
    savepoints above the session's own, and makes the next commit() emit
    "nested transaction already deassociated from connection" (issue #87).

    The anchor savepoint is pysqlite-specific: its legacy transaction mode never
    emits BEGIN for ``connection.begin()``, so without an enclosing SAVEPOINT the
    session's own SAVEPOINT would be the outermost one and SQLite would treat its
    RELEASE as a real COMMIT, leaking rows into later tests.
    """
    connection = engine.connect()
    transaction = connection.begin()
    connection.begin_nested()
    session = TestSession(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient
    from bibmeded.database import get_db
    from bibmeded.main import create_app
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)
