"""Add methodology_steps table

Revision ID: 002
Revises: 001
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"


def upgrade():
    op.create_table(
        "methodology_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("query_id", sa.Integer(), sa.ForeignKey("search_queries.id"), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("phase", sa.String(50), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("records_in", sa.Integer(), nullable=False),
        sa.Column("records_out", sa.Integer(), nullable=False),
        sa.Column("records_affected", sa.Integer(), nullable=False),
        sa.Column("parameters", sa.JSON(), default={}),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("methodology_steps")
