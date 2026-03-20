from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Publication(Base):
    __tablename__ = "publications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pmid: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(Text)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    publication_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_database: Mapped[str] = mapped_column(String(50), default="pubmed")
    citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    journal_id: Mapped[int | None] = mapped_column(ForeignKey("journals.id"), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    query_id: Mapped[int | None] = mapped_column(ForeignKey("search_queries.id"), nullable=True)
    journal: Mapped["Journal | None"] = relationship(back_populates="publications")
    authors: Mapped[list["Author"]] = relationship(secondary="publication_authors", back_populates="publications")
    keywords: Mapped[list["Keyword"]] = relationship(secondary="publication_keywords", back_populates="publications")
