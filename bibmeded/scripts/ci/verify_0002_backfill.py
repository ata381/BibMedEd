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

Also checks 0004_screening_stage: the seeded ``fulltext_unavailable``
exclusion is backfilled to ``full_text``, the other exclusion to
``title_abstract``, included rows keep a NULL stage, and the CHECK constraint
exists.

Also checks 0006_screening_decisions: the table exists with its stage and source CHECK
constraints and holds no rows, because the decision log is never backfilled.

Usage (from bibmeded/ directory, BIBMEDED_DATABASE_URL pointing at Postgres):
    python scripts/ci/verify_0002_backfill.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text

from bibmeded.database import get_engine

# publication id -> expected project_id, derived from the query_id ->
# search_queries.project_id relationship seeded by seed_pre_0002_fixture.py.
EXPECTED_PROJECT_ID_BY_PUBLICATION_ID = {1: 1, 2: 1, 3: 2, 4: 2}

# 0004_screening_stage backfills pre-existing `fulltext_unavailable` exclusions
# as full_text ("Reports not retrieved"), every other exclusion as
# title_abstract, and leaves included records without a stage.
EXPECTED_SCREENING_STAGE_BY_PUBLICATION_ID = {1: None, 2: "title_abstract", 3: None, 4: "full_text"}


def _screening_stage_errors(conn) -> list[str]:
    errors: list[str] = []
    stages = dict(conn.execute(text("SELECT id, screening_stage FROM publications")).fetchall())
    for pub_id, expected in EXPECTED_SCREENING_STAGE_BY_PUBLICATION_ID.items():
        if stages.get(pub_id) != expected:
            errors.append(
                f"publication {pub_id}: screening_stage={stages.get(pub_id)!r}, expected {expected!r}"
            )
    check_exists = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.table_constraints "
            "WHERE table_name = 'publications' AND constraint_type = 'CHECK' "
            "AND constraint_name = 'ck_publications_screening_stage'"
        )
    ).scalar_one()
    if not check_exists:
        errors.append("publications is missing CHECK constraint ck_publications_screening_stage")
    return errors


DECISION_CHECK_CONSTRAINTS = {
    "ck_screening_decisions_screening_stage",
    "ck_screening_decisions_previous_screening_stage",
    "ck_screening_decisions_source",
}


def _screening_decision_errors(conn) -> list[str]:
    exists = conn.execute(
        text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'screening_decisions'")
    ).scalar_one()
    if not exists:
        return ["screening_decisions table is missing after 0006_screening_decisions"]
    errors: list[str] = []
    decision_count = conn.execute(text("SELECT COUNT(*) FROM screening_decisions")).scalar_one()
    if decision_count:
        errors.append(f"screening_decisions has {decision_count} row(s); 0006 must not backfill decisions")
    checks = {
        row[0]
        for row in conn.execute(
            text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_name = 'screening_decisions' AND constraint_type = 'CHECK'"
            )
        )
    }
    for missing in sorted(DECISION_CHECK_CONSTRAINTS - checks):
        errors.append(f"screening_decisions is missing CHECK constraint {missing}")
    return errors


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
        errors.extend(_screening_stage_errors(conn))
        errors.extend(_screening_decision_errors(conn))

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
        "to project_id, NOT NULL enforced; exclusions backfilled to their PRISMA screening stage; "
        "empty screening decision log created."
    )


if __name__ == "__main__":
    main()
