"""Seed a pre-0002 Postgres schema fixture for the CI "Migrations (Postgres)" job.

Recreates the schema exactly as it looked immediately before revision
0002_publication_project_scope (globally-unique ``publications.pmid``, no
``publications.project_id`` column) so CI can then run

    alembic stamp 0001_baseline
    alembic upgrade head

against a database that looks like a real pre-0002 production database, and
exercise the actual project_id backfill / NOT NULL / constraint-swap DDL path
that a from-scratch ``Base.metadata.create_all`` database never touches.

Usage (from bibmeded/ directory, BIBMEDED_DATABASE_URL pointing at Postgres):
    python scripts/ci/seed_pre_0002_fixture.py

WARNING: drops and recreates the ``public`` schema. Only ever run this against
a throwaway CI database.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure app is importable, matching scripts/reset_db.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text

from app.database import get_engine

# Pre-0002 shape, per alembic/versions/0002_publication_project_scope.py's own
# upgrade(): publications has no project_id column and pmid is globally unique
# (op.drop_index/create_index(unique=False) is what turns this into the
# post-migration lookup-only index).
DDL_STATEMENTS = [
    "DROP SCHEMA IF EXISTS public CASCADE",
    "CREATE SCHEMA public",
    """
    CREATE TABLE search_projects (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        date_range_start DATE,
        date_range_end DATE,
        created_at TIMESTAMP DEFAULT now(),
        updated_at TIMESTAMP DEFAULT now()
    )
    """,
    """
    CREATE TABLE search_queries (
        id SERIAL PRIMARY KEY,
        project_id INTEGER NOT NULL REFERENCES search_projects(id) ON DELETE CASCADE,
        query_string TEXT NOT NULL,
        database VARCHAR(50) NOT NULL DEFAULT 'pubmed',
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        result_count INTEGER,
        raw_result_count INTEGER,
        duplicate_count INTEGER,
        created_at TIMESTAMP DEFAULT now(),
        executed_at TIMESTAMP
    )
    """,
    """
    CREATE TABLE publications (
        id SERIAL PRIMARY KEY,
        pmid VARCHAR(50) NOT NULL,
        doi VARCHAR(255),
        title TEXT NOT NULL,
        abstract TEXT,
        year INTEGER,
        publication_type VARCHAR(100),
        source_database VARCHAR(50) NOT NULL DEFAULT 'pubmed',
        citation_count INTEGER,
        journal_id INTEGER,
        fetched_at TIMESTAMP DEFAULT now(),
        query_id INTEGER REFERENCES search_queries(id) ON DELETE CASCADE,
        excluded BOOLEAN NOT NULL DEFAULT false,
        exclusion_reason VARCHAR(100),
        external_references JSONB
    )
    """,
    # Global-unique pmid index, exactly as 0002's downgrade() restores it —
    # i.e. exactly what upgrade() expects to find and replace.
    "CREATE UNIQUE INDEX ix_publications_pmid ON publications (pmid)",
]

# Two projects so the backfill must actually route each publication to the
# project owned by *its own* query, not just stamp a single project_id
# everywhere.
FIXTURE_STATEMENTS = [
    """
    INSERT INTO search_projects (id, name) VALUES
        (1, 'CI fixture project A'),
        (2, 'CI fixture project B')
    """,
    """
    INSERT INTO search_queries (id, project_id, query_string) VALUES
        (1, 1, 'ci fixture query for project A'),
        (2, 2, 'ci fixture query for project B')
    """,
    """
    INSERT INTO publications (id, pmid, title, query_id) VALUES
        (1, '10000001', 'Project A paper 1', 1),
        (2, '10000002', 'Project A paper 2', 1),
        (3, '10000003', 'Project B paper 1', 2)
    """,
]


def main() -> None:
    engine = get_engine()
    print(f"Seeding pre-0002 fixture schema at: {engine.url}")
    with engine.begin() as conn:
        for statement in DDL_STATEMENTS + FIXTURE_STATEMENTS:
            conn.execute(text(statement))
    engine.dispose()
    print("Seeded pre-0002 schema: 2 search_projects, 2 search_queries, 3 publications.")


if __name__ == "__main__":
    main()
