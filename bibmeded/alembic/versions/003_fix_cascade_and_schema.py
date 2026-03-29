"""Fix cascade deletes and analysis_runs schema mismatch

Revision ID: 003
Revises: 002
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"


def upgrade():
    # Fix analysis_runs: add missing 'parameters' column, widen analysis_type, change results to JSON
    op.add_column("analysis_runs", sa.Column("parameters", sa.JSON(), nullable=True))
    op.alter_column("analysis_runs", "analysis_type", type_=sa.String(100))
    # Note: 'results' is stored as text but should be JSON. Alter it:
    op.alter_column("analysis_runs", "results", type_=sa.JSON(), postgresql_using="results::json")

    # Widen pmid column to accommodate OpenAlex IDs
    op.alter_column("publications", "pmid", type_=sa.String(50))

    # Widen affiliation columns — real PubMed affiliations can exceed 500 chars
    op.alter_column("affiliations", "name", type_=sa.Text())
    op.alter_column("affiliations", "name_normalized", type_=sa.Text())

    # Add ON DELETE CASCADE to all FKs in the delete chain:
    # publication_authors → publications
    op.drop_constraint("publication_authors_publication_id_fkey", "publication_authors", type_="foreignkey")
    op.create_foreign_key("publication_authors_publication_id_fkey", "publication_authors", "publications",
                          ["publication_id"], ["id"], ondelete="CASCADE")

    # publication_keywords → publications
    op.drop_constraint("publication_keywords_publication_id_fkey", "publication_keywords", type_="foreignkey")
    op.create_foreign_key("publication_keywords_publication_id_fkey", "publication_keywords", "publications",
                          ["publication_id"], ["id"], ondelete="CASCADE")

    # publications → search_queries
    op.drop_constraint("publications_query_id_fkey", "publications", type_="foreignkey")
    op.create_foreign_key("publications_query_id_fkey", "publications", "search_queries",
                          ["query_id"], ["id"], ondelete="CASCADE")

    # search_queries → search_projects
    op.drop_constraint("search_queries_project_id_fkey", "search_queries", type_="foreignkey")
    op.create_foreign_key("search_queries_project_id_fkey", "search_queries", "search_projects",
                          ["project_id"], ["id"], ondelete="CASCADE")

    # methodology_steps → search_queries
    op.drop_constraint("methodology_steps_query_id_fkey", "methodology_steps", type_="foreignkey")
    op.create_foreign_key("methodology_steps_query_id_fkey", "methodology_steps", "search_queries",
                          ["query_id"], ["id"], ondelete="CASCADE")

    # analysis_runs → search_projects
    op.drop_constraint("analysis_runs_project_id_fkey", "analysis_runs", type_="foreignkey")
    op.create_foreign_key("analysis_runs_project_id_fkey", "analysis_runs", "search_projects",
                          ["project_id"], ["id"], ondelete="CASCADE")


def downgrade():
    # Revert CASCADE to default RESTRICT (reverse order)
    for table, col, ref_table in [
        ("analysis_runs", "project_id", "search_projects"),
        ("methodology_steps", "query_id", "search_queries"),
        ("search_queries", "project_id", "search_projects"),
        ("publications", "query_id", "search_queries"),
        ("publication_keywords", "publication_id", "publications"),
        ("publication_authors", "publication_id", "publications"),
    ]:
        constraint = f"{table}_{col}_fkey"
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(constraint, table, ref_table, [col], ["id"])

    op.drop_column("analysis_runs", "parameters")
    op.alter_column("analysis_runs", "analysis_type", type_=sa.String(50))
    op.alter_column("analysis_runs", "results", type_=sa.Text())
