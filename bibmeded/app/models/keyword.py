import enum
from sqlalchemy import Column, Enum, ForeignKey, Integer, String, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

publication_keywords = Table(
    "publication_keywords", Base.metadata,
    Column("publication_id", Integer, ForeignKey("publications.id", ondelete="CASCADE"), primary_key=True),
    Column("keyword_id", Integer, ForeignKey("keywords.id"), primary_key=True),
)


class KeywordType(str, enum.Enum):
    author_keyword = "author_keyword"
    mesh_term = "mesh_term"


class Keyword(Base):
    __tablename__ = "keywords"
    __table_args__ = (UniqueConstraint("term", "type", name="uq_keywords_term_type"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    term: Mapped[str] = mapped_column(String(255))
    type: Mapped[KeywordType] = mapped_column(
        Enum(KeywordType, create_constraint=False, native_enum=False)
    )
    term_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True)
    publications: Mapped[list["Publication"]] = relationship(
        secondary=publication_keywords, back_populates="keywords"
    )
