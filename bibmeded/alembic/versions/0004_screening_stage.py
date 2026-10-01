"""record the PRISMA 2020 screening stage of each exclusion

Adds ``publications.screening_stage`` (``title_abstract`` | ``full_text``,
NULL while a record is included) with a CHECK constraint on the allowed
values. Every exclusion that exists before this revision was made through the
single-stage UI, which PRISMA 2020 reports as title/abstract screening, so the
backfill stamps those rows ``title_abstract``.

Downgrading drops the column: full-text exclusions stay excluded with their
reason but lose their stage, so export the methodology log first.

Revision ID: 0004_screening_stage
Revises: 0003_sample_project_key
Create Date: 2026-10-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0004_screening_stage"
down_revision: str | None = "0003_sample_project_key"
branch_labels: str | None = None
depends_on: str | None = None

COLUMN_NAME = "screening_stage"
CONSTRAINT_NAME = "ck_publications_screening_stage"
CONSTRAINT_SQL = "screening_stage IS NULL OR screening_stage IN ('title_abstract', 'full_text')"


def _publications_state(bind) -> tuple[bool, set[str], set[str]]:
    inspector = sa.inspect(bind)
    if not inspector.has_table("publications"):
        return False, set(), set()
    columns = {column["name"] for column in inspector.get_columns("publications")}
    checks = {check["name"] for check in inspector.get_check_constraints("publications")}
    return True, columns, checks


def upgrade() -> None:
    # Fresh databases have no tables yet: the entrypoint runs `alembic upgrade
    # head` before create_all builds the current model, so this must no-op.
    has_table, columns, checks = _publications_state(op.get_bind())
    if not has_table:
        return

    if COLUMN_NAME not in columns:
        with op.batch_alter_table("publications") as batch_op:
            batch_op.add_column(sa.Column(COLUMN_NAME, sa.String(length=20), nullable=True))

    publications = sa.table(
        "publications",
        sa.column("excluded", sa.Boolean()),
        sa.column(COLUMN_NAME, sa.String(length=20)),
    )
    op.execute(
        publications.update()
        .where(publications.c.excluded == sa.true())
        .where(publications.c[COLUMN_NAME].is_(None))
        .values({COLUMN_NAME: "title_abstract"})
    )

    if CONSTRAINT_NAME not in checks:
        with op.batch_alter_table("publications") as batch_op:
            batch_op.create_check_constraint(CONSTRAINT_NAME, sa.text(CONSTRAINT_SQL))


def downgrade() -> None:
    has_table, columns, checks = _publications_state(op.get_bind())
    if not has_table:
        return

    with op.batch_alter_table("publications") as batch_op:
        if CONSTRAINT_NAME in checks:
            batch_op.drop_constraint(CONSTRAINT_NAME, type_="check")
        if COLUMN_NAME in columns:
            batch_op.drop_column(COLUMN_NAME)
