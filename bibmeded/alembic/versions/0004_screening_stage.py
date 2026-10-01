"""record the PRISMA 2020 screening stage of each exclusion

Adds ``publications.screening_stage`` (``title_abstract`` | ``full_text``,
NULL while a record is included) with a CHECK constraint on the allowed
values, and backfills every exclusion that predates this revision:

- reason ``fulltext_unavailable`` → ``full_text``: PRISMA 2020 reports a
  report that could not be retrieved under "Reports not retrieved", which only
  exists at the full-text stage;
- every other exclusion → ``title_abstract``: it was made through the
  single-stage UI, which PRISMA 2020 reports as title/abstract screening.

Downgrading drops the column, which would erase the stage of every full-text
exclusion. It refuses to do so while any exist unless
``BIBMEDED_ALLOW_LOSSY_DOWNGRADE=1`` is set.

Revision ID: 0004_screening_stage
Revises: 0003_sample_project_key
Create Date: 2026-10-01
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa


revision: str = "0004_screening_stage"
down_revision: str | None = "0003_sample_project_key"
branch_labels: str | None = None
depends_on: str | None = None

COLUMN_NAME = "screening_stage"
CONSTRAINT_NAME = "ck_publications_screening_stage"
CONSTRAINT_SQL = "screening_stage IS NULL OR screening_stage IN ('title_abstract', 'full_text')"
NOT_RETRIEVED_REASON = "fulltext_unavailable"
LOSSY_DOWNGRADE_ENV_VAR = "BIBMEDED_ALLOW_LOSSY_DOWNGRADE"

_publications = sa.table(
    "publications",
    sa.column("excluded", sa.Boolean()),
    sa.column("exclusion_reason", sa.String(length=100)),
    sa.column(COLUMN_NAME, sa.String(length=20)),
)


def _publications_state(bind) -> tuple[bool, set[str], set[str]]:
    inspector = sa.inspect(bind)
    if not inspector.has_table("publications"):
        return False, set(), set()
    columns = {column["name"] for column in inspector.get_columns("publications")}
    checks = {check["name"] for check in inspector.get_check_constraints("publications")}
    return True, columns, checks


def _backfill_unstaged_exclusions(stage: str, *conditions) -> None:
    op.execute(
        _publications.update()
        .where(_publications.c.excluded == sa.true())
        .where(_publications.c[COLUMN_NAME].is_(None))
        .where(*conditions)
        .values({COLUMN_NAME: stage})
    )


def upgrade() -> None:
    # Fresh databases have no tables yet: the entrypoint runs `alembic upgrade
    # head` before create_all builds the current model, so this must no-op.
    has_table, columns, checks = _publications_state(op.get_bind())
    if not has_table:
        return

    if COLUMN_NAME not in columns:
        with op.batch_alter_table("publications") as batch_op:
            batch_op.add_column(sa.Column(COLUMN_NAME, sa.String(length=20), nullable=True))

    # Order matters: the catch-all below would otherwise claim these rows.
    _backfill_unstaged_exclusions("full_text", _publications.c.exclusion_reason == NOT_RETRIEVED_REASON)
    _backfill_unstaged_exclusions("title_abstract")

    if CONSTRAINT_NAME not in checks:
        with op.batch_alter_table("publications") as batch_op:
            batch_op.create_check_constraint(CONSTRAINT_NAME, sa.text(CONSTRAINT_SQL))


def downgrade() -> None:
    bind = op.get_bind()
    has_table, columns, checks = _publications_state(bind)
    if not has_table:
        return

    if COLUMN_NAME in columns and os.environ.get(LOSSY_DOWNGRADE_ENV_VAR) != "1":
        full_text_count = bind.execute(
            sa.select(sa.func.count()).select_from(_publications).where(_publications.c[COLUMN_NAME] == "full_text")
        ).scalar()
        if full_text_count:
            raise RuntimeError(
                f"0004_screening_stage downgrade: {full_text_count} publication(s) were excluded at the "
                "full-text stage, and dropping publications.screening_stage would erase that stage "
                "(they would read as title/abstract exclusions after re-upgrading). Export the "
                "methodology log and PRISMA diagram for every affected project first, then re-run "
                f"with {LOSSY_DOWNGRADE_ENV_VAR}=1 to accept the loss. Refusing to silently drop "
                "reproducibility-critical screening data."
            )

    with op.batch_alter_table("publications") as batch_op:
        if CONSTRAINT_NAME in checks:
            batch_op.drop_constraint(CONSTRAINT_NAME, type_="check")
        if COLUMN_NAME in columns:
            batch_op.drop_column(COLUMN_NAME)
