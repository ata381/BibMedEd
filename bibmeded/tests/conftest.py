import os

# Set SQLite URL before any app imports to avoid needing psycopg2 during tests.
# pydantic-settings reads env vars when Settings() is instantiated (at config import time),
# so this must be set before app.config is first imported.
os.environ["BIBMEDED_DATABASE_URL"] = "sqlite://"

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    from app.database import Base
    import app.models  # noqa: F401 – ensures all models are registered on Base.metadata
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db():
    """Provide a transactional database session that rolls back after each test.

    Uses the nested transaction (savepoint) pattern so that even when
    application code calls session.commit(), the data is committed only
    to the savepoint and the outer transaction is rolled back at teardown.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestSession(bind=connection)

    # Begin a nested (savepoint) transaction.
    nested = connection.begin_nested()

    # When the application code calls session.commit(), SQLAlchemy ends the
    # savepoint. We listen for that event and start a new savepoint so that
    # subsequent commits within the same test also stay inside the outer
    # transaction.
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, trans):
        nonlocal nested
        if trans.nested and not trans._parent.nested:
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient
    from app.database import get_db
    from app.main import create_app
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)
