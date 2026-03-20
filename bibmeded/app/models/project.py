import enum
from datetime import date, datetime
from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class SearchProject(Base):
    __tablename__ = "search_projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_range_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_range_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    queries: Mapped[list["SearchQuery"]] = relationship(back_populates="project")


class QueryStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class SearchQuery(Base):
    __tablename__ = "search_queries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("search_projects.id"))
    query_string: Mapped[str] = mapped_column(Text)
    database: Mapped[str] = mapped_column(String(50), default="pubmed")
    status: Mapped[QueryStatus] = mapped_column(
        Enum(QueryStatus, create_constraint=False, native_enum=False),
        default=QueryStatus.pending,
    )
    result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    project: Mapped["SearchProject"] = relationship(back_populates="queries")
