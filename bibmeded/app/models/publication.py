from datetime import datetime
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Publication(Base):
    __tablename__ = "publications"
    # Identifiers are unique PER PROJECT, not globally: each systematic-review
    # project owns its own copy of a shared paper (with its own screening/excluded
    # state), so the same PMID/DOI legitimately appears once per project.
    # NULL doi rows are treated as distinct by both Postgres and SQLite, so
    # DOI-less records within a project never collide on the doi constraint.
    __table_args__ = (
        UniqueConstraint("project_id", "pmid", name="uq_publications_project_pmid"),
        UniqueConstraint("project_id", "doi", name="uq_publications_project_doi"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pmid: Mapped[str] = mapped_column(String(50), index=True)
    # `doi` is the cross-source dedup key and the coupling/co-citation join target —
    # indexed so the bibliographic-coupling lookup at analysis time is sublinear.
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    publication_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_database: Mapped[str] = mapped_column(String(50), default="pubmed")
    citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    journal_id: Mapped[int | None] = mapped_column(ForeignKey("journals.id"), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # `query_id` is the hot filter for list_publications, bulk_exclude, and every
    # analysis function — without an index every request is a full table scan.
    query_id: Mapped[int | None] = mapped_column(ForeignKey("search_queries.id", ondelete="CASCADE"), nullable=True, index=True)
    # Denormalized from query→project so per-project identifier uniqueness can be
    # enforced by a composite constraint (a UNIQUE constraint can't span tables).
    project_id: Mapped[int] = mapped_column(ForeignKey("search_projects.id", ondelete="CASCADE"), index=True)
    excluded: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", index=True)
    exclusion_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Raw reference list from the adapter. Each entry is a source-native identifier
    # (PMID for PubMed, DOI for CrossRef, OpenAlex ID for OpenAlex). Used at analysis
    # time to build bibliographic-coupling and co-citation networks against in-corpus
    # publications.
    external_references: Mapped[list | None] = mapped_column(JSON, nullable=True)
    journal: Mapped["Journal | None"] = relationship(back_populates="publications")
    authors: Mapped[list["Author"]] = relationship(secondary="publication_authors", back_populates="publications")
    keywords: Mapped[list["Keyword"]] = relationship(secondary="publication_keywords", back_populates="publications")
    outgoing_citations: Mapped[list["Citation"]] = relationship(foreign_keys="Citation.citing_publication_id", back_populates="citing_publication")
    incoming_citations: Mapped[list["Citation"]] = relationship(foreign_keys="Citation.cited_publication_id", back_populates="cited_publication")
