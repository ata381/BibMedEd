"""publication per-project scoping

Denormalizes ``project_id`` onto ``publications`` (backfilled from
``search_queries.project_id``) and replaces the global-unique constraint on
``pmid`` with composite per-project uniqueness on ``(project_id, pmid)`` and
``(project_id, doi)``. This lets each systematic-review project own its own copy
of a shared paper instead of the first project to ingest a PMID claiming it
globally and starving every later project of that record.

Targets Postgres (production). Dev/CI create the schema via
``Base.metadata.create_all`` and never run this migration.

Revision ID: 0002_publication_project_scope
Revises: 0001_baseline
Create Date: 2026-07-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_publication_project_scope"
down_revision: str | None = "0001_baseline"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Fresh databases (new Docker volume): the entrypoint runs `alembic upgrade
    # head` BEFORE the compose command's `Base.metadata.create_all`, so no tables
    # exist yet at this point. create_all will build the current model — which
    # already includes project_id and the composite constraints — so this
    # migration must no-op; it only has work to do on databases that hold the
    # pre-0002 schema (per the 0001_baseline contract).
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("publications"):
        return

    # 1. Add project_id nullable so existing rows can be backfilled first.
    op.add_column("publications", sa.Column("project_id", sa.Integer(), nullable=True))

    # 2. Backfill from the owning query's project.
    op.execute(
        """
        UPDATE publications
        SET project_id = sq.project_id
        FROM search_queries sq
        WHERE publications.query_id = sq.id
        """
    )

    # 3. Enforce NOT NULL + FK once every row has a project.
    op.alter_column("publications", "project_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(
        "fk_publications_project_id_search_projects",
        "publications",
        "search_projects",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_publications_project_id", "publications", ["project_id"])

    # 4. Swap the global-unique pmid index for a plain lookup index, then add the
    #    per-project composite unique constraints.
    op.drop_index("ix_publications_pmid", table_name="publications")
    op.create_index("ix_publications_pmid", "publications", ["pmid"], unique=False)
    op.create_unique_constraint(
        "uq_publications_project_pmid", "publications", ["project_id", "pmid"]
    )
    op.create_unique_constraint(
        "uq_publications_project_doi", "publications", ["project_id", "doi"]
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("publications"):
        return

    op.drop_constraint("uq_publications_project_doi", "publications", type_="unique")
    op.drop_constraint("uq_publications_project_pmid", "publications", type_="unique")
    op.drop_index("ix_publications_pmid", table_name="publications")
    op.create_index("ix_publications_pmid", "publications", ["pmid"], unique=True)

    op.drop_index("ix_publications_project_id", table_name="publications")
    op.drop_constraint(
        "fk_publications_project_id_search_projects", "publications", type_="foreignkey"
    )
    op.drop_column("publications", "project_id")
