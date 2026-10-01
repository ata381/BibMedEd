"""Alembic migration tests against a throwaway SQLite file.

Postgres is exercised by the CI "Migrations (Postgres)" job; these tests cover
the SQLite path used by the read-only demo and local `alembic upgrade head`.
"""

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from bibmeded.config import settings

ALEMBIC_DIR = Path(__file__).resolve().parents[1] / "alembic"

PRE_0004_DDL = [
    "CREATE TABLE search_projects (id INTEGER PRIMARY KEY, name VARCHAR(255) NOT NULL, sample_key VARCHAR(100))",
    "CREATE TABLE search_queries (id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES search_projects(id), query_string TEXT NOT NULL)",
    """
    CREATE TABLE publications (
        id INTEGER PRIMARY KEY,
        pmid VARCHAR(50) NOT NULL,
        doi VARCHAR(255),
        title TEXT NOT NULL,
        query_id INTEGER REFERENCES search_queries(id) ON DELETE CASCADE,
        project_id INTEGER NOT NULL REFERENCES search_projects(id) ON DELETE CASCADE,
        excluded BOOLEAN NOT NULL DEFAULT 0,
        exclusion_reason VARCHAR(100),
        CONSTRAINT uq_publications_project_pmid UNIQUE (project_id, pmid),
        CONSTRAINT uq_publications_project_doi UNIQUE (project_id, doi)
    )
    """,
    "CREATE INDEX ix_publications_excluded ON publications (excluded)",
    "INSERT INTO search_projects (id, name) VALUES (1, 'p')",
    "INSERT INTO search_queries (id, project_id, query_string) VALUES (1, 1, 'q')",
    """
    INSERT INTO publications (id, pmid, title, query_id, project_id, excluded, exclusion_reason) VALUES
        (1, 'a', 'Excluded with reason', 1, 1, 1, 'non_english'),
        (2, 'b', 'Excluded without reason', 1, 1, 1, NULL),
        (3, 'c', 'Included', 1, 1, 0, NULL)
    """,
]


@pytest.fixture
def sqlite_db(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'migrate.db').as_posix()}"
    monkeypatch.setattr(settings, "database_url", url)
    engine = sa.create_engine(url)
    yield engine
    engine.dispose()


def _alembic_config() -> Config:
    # No ini file on purpose: env.py would call logging.fileConfig on it and
    # disable every logger other tests rely on.
    config = Config()
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    return config


def _columns(engine, table="publications") -> set[str]:
    return {c["name"] for c in sa.inspect(engine).get_columns(table)}


def _seed_pre_0004(engine) -> None:
    with engine.begin() as conn:
        for statement in PRE_0004_DDL:
            conn.execute(sa.text(statement))


def test_0004_backfills_existing_exclusions_as_title_abstract(sqlite_db):
    _seed_pre_0004(sqlite_db)
    config = _alembic_config()
    command.stamp(config, "0003_sample_project_key")

    command.upgrade(config, "0004_screening_stage")

    assert "screening_stage" in _columns(sqlite_db)
    with sqlite_db.connect() as conn:
        rows = conn.execute(
            sa.text("SELECT id, excluded, exclusion_reason, screening_stage FROM publications ORDER BY id")
        ).fetchall()
    assert [tuple(r) for r in rows] == [
        (1, 1, "non_english", "title_abstract"),
        (2, 1, None, "title_abstract"),
        (3, 0, None, None),
    ]


def test_0004_rejects_unknown_screening_stage(sqlite_db):
    _seed_pre_0004(sqlite_db)
    config = _alembic_config()
    command.stamp(config, "0003_sample_project_key")
    command.upgrade(config, "0004_screening_stage")

    with pytest.raises(sa.exc.IntegrityError):
        with sqlite_db.begin() as conn:
            conn.execute(sa.text("UPDATE publications SET screening_stage = 'abstract' WHERE id = 3"))


def test_0004_downgrade_drops_column_and_keeps_rows(sqlite_db):
    _seed_pre_0004(sqlite_db)
    config = _alembic_config()
    command.stamp(config, "0003_sample_project_key")
    command.upgrade(config, "0004_screening_stage")

    command.downgrade(config, "0003_sample_project_key")

    assert "screening_stage" not in _columns(sqlite_db)
    with sqlite_db.connect() as conn:
        rows = conn.execute(sa.text("SELECT id, excluded, exclusion_reason FROM publications ORDER BY id")).fetchall()
    assert [tuple(r) for r in rows] == [(1, 1, "non_english"), (2, 1, None), (3, 0, None)]


def test_0004_is_a_no_op_on_an_empty_database(sqlite_db):
    command.upgrade(_alembic_config(), "head")
    assert not sa.inspect(sqlite_db).has_table("publications")


def test_0004_is_idempotent_on_a_create_all_schema(sqlite_db):
    from bibmeded.database import Base
    import bibmeded.models  # noqa: F401

    Base.metadata.create_all(sqlite_db)
    config = _alembic_config()
    command.stamp(config, "0003_sample_project_key")

    command.upgrade(config, "head")
    command.downgrade(config, "0003_sample_project_key")
    command.upgrade(config, "head")

    assert "screening_stage" in _columns(sqlite_db)
