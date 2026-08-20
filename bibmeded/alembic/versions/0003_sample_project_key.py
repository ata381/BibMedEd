"""add a unique marker for the bundled sample project

Revision ID: 0003_sample_project_key
Revises: 0002_publication_project_scope
Create Date: 2026-08-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0003_sample_project_key"
down_revision: str | None = "0002_publication_project_scope"
branch_labels: str | None = None
depends_on: str | None = None

CONSTRAINT_NAME = "uq_search_projects_sample_key"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("search_projects"):
        return

    columns = {column["name"] for column in inspector.get_columns("search_projects")}
    constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("search_projects")
    }
    with op.batch_alter_table("search_projects") as batch_op:
        if "sample_key" not in columns:
            batch_op.add_column(
                sa.Column("sample_key", sa.String(length=100), nullable=True)
            )
        if CONSTRAINT_NAME not in constraints:
            batch_op.create_unique_constraint(CONSTRAINT_NAME, ["sample_key"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("search_projects"):
        return

    constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("search_projects")
    }
    columns = {column["name"] for column in inspector.get_columns("search_projects")}
    with op.batch_alter_table("search_projects") as batch_op:
        if CONSTRAINT_NAME in constraints:
            batch_op.drop_constraint(CONSTRAINT_NAME, type_="unique")
        if "sample_key" in columns:
            batch_op.drop_column("sample_key")
