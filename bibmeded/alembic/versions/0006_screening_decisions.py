"""add the append-only screening decision log

Creates ``screening_decisions``: one row per change to a publication's
screening state (``excluded`` / ``exclusion_reason`` / ``screening_stage``),
with the UTC time, an optional free-text reviewer label, the endpoint that made
it (``source``, restricted by a CHECK), a ``run_id`` shared by every row of one
bulk request, the criteria of a bulk exclusion, and the state before and after.

Nothing is backfilled. When and by whom earlier exclusions were made was never
recorded, so the methodology export says the log starts at this revision and
counts current exclusions that have no logged decision.

Downgrading drops the table and every logged decision with it. It refuses to do
so while any exist unless ``BIBMEDED_ALLOW_LOSSY_DOWNGRADE=1`` is set. The
``bulk_exclude`` methodology steps written alongside the log live in
``methodology_steps`` and are kept; code from before this revision prints them
as an extra pipeline phase.

Revision ID: 0006_screening_decisions
Revises: 0005_sample_query_string
Create Date: 2026-10-12
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa


revision: str = "0006_screening_decisions"
down_revision: str | None = "0005_sample_query_string"
branch_labels: str | None = None
depends_on: str | None = None

TABLE_NAME = "screening_decisions"
STAGE_CHECK_SQL = "{column} IS NULL OR {column} IN ('title_abstract', 'full_text')"
# Frozen copy of bibmeded.models.screening.SCREENING_DECISION_SOURCES.
SOURCE_CHECK_SQL = "source IN ('toggle', 'bulk_exclude', 'sample_seed')"
PROJECT_RUN_INDEX = "ix_screening_decisions_project_id_run_id"
PUBLICATION_INDEX = "ix_screening_decisions_publication_id"
LOSSY_DOWNGRADE_ENV_VAR = "BIBMEDED_ALLOW_LOSSY_DOWNGRADE"


def _has_table(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def upgrade() -> None:
    bind = op.get_bind()
    # Fresh databases have no tables yet: the entrypoint runs `alembic upgrade
    # head` before create_all builds the current model, so this must no-op. A
    # create_all database already has the table.
    if not _has_table(bind, "publications") or _has_table(bind, TABLE_NAME):
        return

    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("search_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "publication_id",
            sa.Integer(),
            sa.ForeignKey("publications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewer", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("criteria", sa.JSON(), nullable=True),
        sa.Column("previous_excluded", sa.Boolean(), nullable=False),
        sa.Column("previous_exclusion_reason", sa.String(length=100), nullable=True),
        sa.Column("previous_screening_stage", sa.String(length=20), nullable=True),
        sa.Column("excluded", sa.Boolean(), nullable=False),
        sa.Column("exclusion_reason", sa.String(length=100), nullable=True),
        sa.Column("screening_stage", sa.String(length=20), nullable=True),
        sa.CheckConstraint(
            STAGE_CHECK_SQL.format(column="screening_stage"),
            name="ck_screening_decisions_screening_stage",
        ),
        sa.CheckConstraint(
            STAGE_CHECK_SQL.format(column="previous_screening_stage"),
            name="ck_screening_decisions_previous_screening_stage",
        ),
        sa.CheckConstraint(SOURCE_CHECK_SQL, name="ck_screening_decisions_source"),
    )
    op.create_index(PROJECT_RUN_INDEX, TABLE_NAME, ["project_id", "run_id"])
    op.create_index(PUBLICATION_INDEX, TABLE_NAME, ["publication_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, TABLE_NAME):
        return

    if os.environ.get(LOSSY_DOWNGRADE_ENV_VAR) != "1":
        decision_count = bind.execute(sa.text(f"SELECT COUNT(*) FROM {TABLE_NAME}")).scalar()
        if decision_count:
            raise RuntimeError(
                f"0006_screening_decisions downgrade: {decision_count} screening decision(s) are logged, "
                "and dropping screening_decisions would erase who changed which record's screening "
                "state, when, and from what. Export the methodology log and bundle (which carries the "
                "per-decision CSV) for every affected project first, then re-run with "
                f"{LOSSY_DOWNGRADE_ENV_VAR}=1 to accept the loss. Refusing to silently drop "
                "reproducibility-critical screening data."
            )

    op.drop_index(PUBLICATION_INDEX, table_name=TABLE_NAME)
    op.drop_index(PROJECT_RUN_INDEX, table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)
