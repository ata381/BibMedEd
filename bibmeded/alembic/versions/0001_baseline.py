"""baseline — current schema as of v0.2.0

This is the BASELINE migration. It is intentionally a no-op: it captures the
current `Base.metadata` state so existing dev/CI databases that were created
via SQLAlchemy `create_all` can be `alembic stamp head`'d into Alembic's view
of the world, after which all future schema changes ship as additive migrations
on top of this revision.

For a fresh production deploy:

    alembic upgrade head

For an existing dev/CI database that was created via `create_all` and is
already on the v0.2.0 schema:

    alembic stamp 0001_baseline

Subsequent schema additions (new columns, indexes, tables) will be normal
`alembic revision --autogenerate` migrations targeting this revision as
their parent.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-28
"""

from __future__ import annotations

from alembic import op  # noqa: F401 — kept for symmetric upgrade/downgrade scaffolding
import sqlalchemy as sa  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """No-op. Schema is assumed already created via SQLAlchemy `create_all` in
    dev/CI environments and via this baseline being applied to fresh production
    databases. Future migrations target `0001_baseline` as their parent.

    For a fresh production database, run `alembic upgrade head` AFTER the
    initial `Base.metadata.create_all` (or use `create_all` directly and then
    `alembic stamp head` — both end up in the same state).
    """
    pass


def downgrade() -> None:
    """No downgrade — this is the baseline."""
    pass
