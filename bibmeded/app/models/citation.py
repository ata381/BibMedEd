from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Citation(Base):
    __tablename__ = "citations"
    citing_publication_id: Mapped[int] = mapped_column(Integer, ForeignKey("publications.id"), primary_key=True)
    cited_publication_id: Mapped[int] = mapped_column(Integer, ForeignKey("publications.id"), primary_key=True)
    citing_publication: Mapped["Publication"] = relationship(foreign_keys=[citing_publication_id], back_populates="outgoing_citations")
    cited_publication: Mapped["Publication"] = relationship(foreign_keys=[cited_publication_id], back_populates="incoming_citations")
