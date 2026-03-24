import os

# Set SQLite URL before any app imports to avoid needing psycopg2 during tests.
# pydantic-settings reads env vars when Settings() is instantiated (at config import time),
# so this must be set before app.config is first imported.
os.environ["BIBMEDED_DATABASE_URL"] = "sqlite://"

import pytest
from sqlalchemy import create_engine
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
    session = TestSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient
    from app.database import get_db
    from app.main import create_app
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)
