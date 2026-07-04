"""Verify the 0002 migration correctly backfilled publications.project_id.

Run after (in order):
    python scripts/ci/seed_pre_0002_fixture.py
    alembic stamp 0001_baseline
    alembic upgrade head

Asserts that every publication seeded by seed_pre_0002_fixture.py ended up
with project_id equal to the project owning its query, that no row was left
NULL, and that the column is now NOT NULL — i.e. that the real backfill /
constraint-enforcement DDL in 0002_publication_project_scope.upgrade() ran
against pre-existing data, not just the fresh-database no-op guard path.

Usage (from bibmeded/ directory, BIBMEDED_DATABASE_URL pointing at Postgres):
    python scripts/ci/verify_0002_backfill.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text

from app.database import get_engine

# publication id -> expected project_id, derived from the query_id ->
# search_queries.project_id relationship seeded by seed_pre_0002_fixture.py.
EXPECTED_PROJECT_ID_BY_PUBLICATION_ID = {1: 1, 2: 1, 3: 2}


def main() -> None:
    engine = get_engine()
    errors: list[str] = []

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, query_id, project_id FROM publications ORDER BY id")
        ).fetchall()
        is_nullable = conn.execute(
            text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'publications' AND column_name = 'project_id'"
            )
        ).scalar_one()

    if len(rows) != len(EXPECTED_PROJECT_ID_BY_PUBLICATION_ID):
        errors.append(
            f"expected {len(EXPECTED_PROJECT_ID_BY_PUBLICATION_ID)} publications, "
            f"found {len(rows)}: {rows}"
        )

    for pub_id, query_id, project_id in rows:
        expected = EXPECTED_PROJECT_ID_BY_PUBLICATION_ID.get(pub_id)
        if project_id is None:
            errors.append(f"publication {pub_id} (query_id={query_id}): project_id is NULL after backfill")
        elif project_id != expected:
            errors.append(
                f"publication {pub_id} (query_id={query_id}): "
                f"project_id={project_id!r}, expected {expected!r}"
            )

    if is_nullable != "NO":
        errors.append(
            f"publications.project_id.is_nullable={is_nullable!r}, expected 'NO' "
            "(0002 must enforce NOT NULL once every row has been backfilled)"
        )

    if errors:
        print("Migration backfill verification FAILED:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    print(
        f"Migration backfill verified: {len(rows)} publications correctly scoped "
        "to project_id, NOT NULL enforced."
    )


if __name__ == "__main__":
    main()
