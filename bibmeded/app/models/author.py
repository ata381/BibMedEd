from sqlalchemy import Column, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

publication_authors = Table(
    "publication_authors", Base.metadata,
    Column("publication_id", Integer, ForeignKey("publications.id", ondelete="CASCADE"), primary_key=True),
    Column("author_id", Integer, ForeignKey("authors.id"), primary_key=True),
    Column("author_position", Integer),
)

author_affiliations = Table(
    "author_affiliations", Base.metadata,
    Column("author_id", Integer, ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True),
    Column("affiliation_id", Integer, ForeignKey("affiliations.id", ondelete="CASCADE"), primary_key=True),
)


class Author(Base):
    __tablename__ = "authors"
    __table_args__ = (UniqueConstraint("orcid", name="uq_authors_orcid"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    orcid: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    # `name_normalized` is the per-batch lookup key in the ingestion path; the bulk
    # prefetch in workers.tasks issues a `WHERE name_normalized IN (...)` per batch.
    name_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    publications: Mapped[list["Publication"]] = relationship(secondary=publication_authors, back_populates="authors")
    affiliations: Mapped[list["Affiliation"]] = relationship(secondary=author_affiliations, back_populates="authors")


class Affiliation(Base):
    __tablename__ = "affiliations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    # Affiliation strings are long ("Department of Internal Medicine, X University,
    # ...") so a btree index over the full Text column is impractical in Postgres
    # (`btree row length limit`). Index just the first 255 chars via a SQLAlchemy
    # Index(func.substr(...)) when Postgres-only support is needed; for now match
    # the lookup pattern (equality on the whole normalized string) and accept the
    # scan cost since Affiliation is a smaller table than Author/Keyword.
    name_normalized: Mapped[str | None] = mapped_column(Text, nullable=True)
    authors: Mapped[list["Author"]] = relationship(secondary=author_affiliations, back_populates="affiliations")
