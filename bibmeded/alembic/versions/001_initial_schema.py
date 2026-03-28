"""initial schema with all current models

Revision ID: 001
Revises:
Create Date: 2026-03-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "search_projects",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("date_range_start", sa.Date, nullable=True),
        sa.Column("date_range_end", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "search_queries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("search_projects.id"), nullable=False),
        sa.Column("query_string", sa.Text, nullable=False),
        sa.Column("database", sa.String(50), server_default="pubmed"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("result_count", sa.Integer, nullable=True),
        sa.Column("raw_result_count", sa.Integer, nullable=True),
        sa.Column("duplicate_count", sa.Integer, nullable=True),
        sa.Column("executed_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "journals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("issn", sa.String(20), nullable=True),
        sa.Column("name_normalized", sa.String(500), nullable=True),
    )

    op.create_table(
        "publications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("pmid", sa.String(20), unique=True, index=True, nullable=False),
        sa.Column("doi", sa.String(255), nullable=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("abstract", sa.Text, nullable=True),
        sa.Column("year", sa.Integer, nullable=True, index=True),
        sa.Column("publication_type", sa.String(100), nullable=True),
        sa.Column("source_database", sa.String(50), server_default="pubmed"),
        sa.Column("citation_count", sa.Integer, nullable=True),
        sa.Column("journal_id", sa.Integer, sa.ForeignKey("journals.id"), nullable=True),
        sa.Column("fetched_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("query_id", sa.Integer, sa.ForeignKey("search_queries.id"), nullable=True),
        sa.Column("excluded", sa.Boolean, server_default="false", nullable=False),
    )

    op.create_table(
        "authors",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("orcid", sa.String(50), nullable=True),
        sa.Column("name_normalized", sa.String(500), nullable=True),
    )

    op.create_table(
        "affiliations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("country", sa.String(255), nullable=True),
        sa.Column("name_normalized", sa.Text, nullable=True),
    )

    op.create_table(
        "keywords",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("term", sa.String(500), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("term_normalized", sa.String(500), nullable=True),
    )

    op.create_table(
        "publication_authors",
        sa.Column("publication_id", sa.Integer, sa.ForeignKey("publications.id"), primary_key=True),
        sa.Column("author_id", sa.Integer, sa.ForeignKey("authors.id"), primary_key=True),
        sa.Column("author_position", sa.Integer, nullable=True),
    )

    op.create_table(
        "publication_keywords",
        sa.Column("publication_id", sa.Integer, sa.ForeignKey("publications.id"), primary_key=True),
        sa.Column("keyword_id", sa.Integer, sa.ForeignKey("keywords.id"), primary_key=True),
    )

    op.create_table(
        "author_affiliations",
        sa.Column("author_id", sa.Integer, sa.ForeignKey("authors.id"), primary_key=True),
        sa.Column("affiliation_id", sa.Integer, sa.ForeignKey("affiliations.id"), primary_key=True),
    )

    op.create_table(
        "citations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("citing_publication_id", sa.Integer, sa.ForeignKey("publications.id"), nullable=False),
        sa.Column("cited_publication_id", sa.Integer, sa.ForeignKey("publications.id"), nullable=False),
    )

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("search_projects.id"), nullable=False),
        sa.Column("analysis_type", sa.String(50), nullable=False),
        sa.Column("results", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("analysis_runs")
    op.drop_table("citations")
    op.drop_table("author_affiliations")
    op.drop_table("publication_keywords")
    op.drop_table("publication_authors")
    op.drop_table("keywords")
    op.drop_table("affiliations")
    op.drop_table("authors")
    op.drop_table("publications")
    op.drop_table("journals")
    op.drop_table("search_queries")
    op.drop_table("search_projects")
