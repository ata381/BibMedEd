from sqlalchemy import Column, ForeignKey, Integer, String, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

publication_authors = Table(
    "publication_authors", Base.metadata,
    Column("publication_id", Integer, ForeignKey("publications.id"), primary_key=True),
    Column("author_id", Integer, ForeignKey("authors.id"), primary_key=True),
    Column("author_position", Integer),
)

author_affiliations = Table(
    "author_affiliations", Base.metadata,
    Column("author_id", Integer, ForeignKey("authors.id"), primary_key=True),
    Column("affiliation_id", Integer, ForeignKey("affiliations.id"), primary_key=True),
)


class Author(Base):
    __tablename__ = "authors"
    __table_args__ = (UniqueConstraint("orcid", name="uq_authors_orcid"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    orcid: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    name_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True)
    publications: Mapped[list["Publication"]] = relationship(secondary=publication_authors, back_populates="authors")
    affiliations: Mapped[list["Affiliation"]] = relationship(secondary=author_affiliations, back_populates="authors")


class Affiliation(Base):
    __tablename__ = "affiliations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name_normalized: Mapped[str | None] = mapped_column(String(500), nullable=True)
    authors: Mapped[list["Author"]] = relationship(secondary=author_affiliations, back_populates="affiliations")
