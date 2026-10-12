"""give existing bundled sample projects the stored search strategy

The bundled sample project used to store the placeholder ``Bundled synthetic
demonstration corpus`` as its query string. It is now seeded with a PubMed-style
strategy that the Search page loads into the raw query editor, but the sample is
reused by ``sample_key``, so a database that seeded it earlier would keep the
placeholder and show that in the editor instead.

Only the seeded row is rewritten: a query of the bundled sample project, stored
against the ``sample`` database, whose text is still exactly the placeholder.
Searches a user ran inside the sample project and every other project are left
alone.

Downgrading changes nothing. An upgraded row is indistinguishable from one
seeded with the strategy, and restoring the placeholder would also rewrite
samples that never held it.

Revision ID: 0005_sample_query_string
Revises: 0004_screening_stage
Create Date: 2026-10-11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0005_sample_query_string"
down_revision: str | None = "0004_screening_stage"
branch_labels: str | None = None
depends_on: str | None = None

# Frozen copies: this revision must keep rewriting to the same text even if
# bibmeded.services.sample_project changes later.
SAMPLE_PROJECT_KEY = "bundled-ai-medical-education-v1"
SAMPLE_DATABASE = "sample"
PLACEHOLDER_QUERY_STRING = "Bundled synthetic demonstration corpus"
SAMPLE_QUERY_STRING = (
    '("Education, Medical"[Mesh] OR "medical education"[tiab]) AND '
    '("Artificial Intelligence"[Mesh] OR "machine learning"[tiab] OR "generative AI"[tiab] '
    'OR "learning analytics"[tiab] OR "simulation"[tiab] OR "virtual patient*"[tiab]) AND '
    '("2018/01/01"[PDAT] : "2025/12/31"[PDAT])'
)

_search_projects = sa.table(
    "search_projects",
    sa.column("id", sa.Integer()),
    sa.column("sample_key", sa.String(length=100)),
)
_search_queries = sa.table(
    "search_queries",
    sa.column("project_id", sa.Integer()),
    sa.column("query_string", sa.Text()),
    sa.column("database", sa.String(length=50)),
)


def upgrade() -> None:
    # Fresh databases have no tables yet: the entrypoint runs `alembic upgrade
    # head` before create_all builds the current model, so this must no-op.
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("search_projects") or not inspector.has_table("search_queries"):
        return

    sample_project_ids = sa.select(_search_projects.c.id).where(
        _search_projects.c.sample_key == SAMPLE_PROJECT_KEY
    )
    op.execute(
        _search_queries.update()
        .where(_search_queries.c.project_id.in_(sample_project_ids))
        .where(_search_queries.c.database == SAMPLE_DATABASE)
        .where(_search_queries.c.query_string == PLACEHOLDER_QUERY_STRING)
        .values(query_string=SAMPLE_QUERY_STRING)
    )


def downgrade() -> None:
    pass
