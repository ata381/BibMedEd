from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Journal(Base):
    __tablename__ = "journals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    issn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    e_issn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    name_normalized: Mapped[str | None] = mapped_column(String(500), nullable=True)
    publications: Mapped[list["Publication"]] = relationship(back_populates="journal")
