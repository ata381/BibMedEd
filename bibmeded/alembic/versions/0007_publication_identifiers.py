"""Separate PubMed IDs from source-native identifiers without discarding IDs."""
import os
from alembic import op
import sqlalchemy as sa

revision = "0007_publication_identifiers"
down_revision = "0006_screening_decisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("publications"):
        return
    columns = {c["name"] for c in inspector.get_columns("publications")}
    if "external_ids" in columns:
        return
    with op.batch_alter_table("publications") as batch:
        batch.add_column(sa.Column("external_ids", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("source_id", sa.String(255), nullable=True))
        batch.alter_column("pmid", existing_type=sa.String(50), nullable=True)
        if "source_database" in columns:
            batch.create_unique_constraint("uq_publications_project_source", ["project_id", "source_database", "source_id"])
    publications = sa.table("publications", sa.column("id", sa.Integer()),
                            sa.column("pmid", sa.String()), sa.column("external_ids", sa.JSON()),
                            sa.column("source_id", sa.String()))
    # Some historical test/demo schemas lack source_database; those rows retain
    # their original value rather than guessing the identifier's provenance.
    if "source_database" not in columns:
        return
    rows = bind.execute(sa.text("SELECT id, pmid, source_database FROM publications")).mappings()
    for row in rows:
        native = row["pmid"]
        source = row["source_database"] or "pubmed"
        identifiers = {source: native} if native else {}
        pmid = native if source == "pubmed" and native and native.isascii() and native.isdecimal() else None
        if pmid:
            identifiers["pmid"] = pmid
        bind.execute(publications.update().where(publications.c.id == row["id"])
                     .values(pmid=pmid, source_id=native, external_ids=identifiers))


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("publications"):
        return
    table = sa.Table("publications", sa.MetaData(), autoload_with=bind)
    rows = bind.execute(sa.select(table)).mappings().all()
    restored = []
    for row in rows:
        source = row.get("source_database") or "pubmed"
        identifiers = row["external_ids"] or {}
        native = identifiers.get(source) or row["pmid"]
        if not native:
            raise RuntimeError("Cannot restore the required source-native identifier; restore a database backup.")
        extra = set(identifiers) - {source, "pmid" if source == "pubmed" else source}
        if extra and os.environ.get("BIBMEDED_ALLOW_LOSSY_DOWNGRADE") != "1":
            raise RuntimeError("Downgrade would discard identifier aliases; set BIBMEDED_ALLOW_LOSSY_DOWNGRADE=1 only after backing up.")
        restored.append((row["id"], native))
    for row_id, native in restored:
        bind.execute(table.update().where(table.c.id == row_id).values(pmid=native))
    with op.batch_alter_table("publications") as batch:
        if "source_database" in table.c:
            batch.drop_constraint("uq_publications_project_source", type_="unique")
        batch.alter_column("pmid", existing_type=sa.String(50), nullable=False)
        batch.drop_column("external_ids")
        batch.drop_column("source_id")
