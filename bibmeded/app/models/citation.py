from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Citation(Base):
    __tablename__ = "citations"
    citing_publication_id: Mapped[int] = mapped_column(Integer, ForeignKey("publications.id"), primary_key=True)
    cited_publication_id: Mapped[int] = mapped_column(Integer, ForeignKey("publications.id"), primary_key=True)
