from datetime import datetime
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class MethodologyStep(Base):
    __tablename__ = "methodology_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query_id: Mapped[int] = mapped_column(ForeignKey("search_queries.id", ondelete="CASCADE"))
    step_order: Mapped[int] = mapped_column(Integer)
    phase: Mapped[str] = mapped_column(String(50))
    source: Mapped[str] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(Text)
    records_in: Mapped[int] = mapped_column(Integer)
    records_out: Mapped[int] = mapped_column(Integer)
    records_affected: Mapped[int] = mapped_column(Integer)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime)

    query: Mapped["SearchQuery"] = relationship(back_populates="methodology_steps")
