from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Citation(Base):
    """Directed intra-corpus citation edge (citing → cited).

    RESERVED / not yet populated by the ingestion pipeline. `analyze_citations`
    queries this table to build the directed `citation_network`, which is empty
    until an ingestion step writes edges here. The bibliographic-coupling and
    co-citation networks shipped in v0.2.0 do NOT depend on this table — they are
    computed from `Publication.external_references`. Wiring up explicit citation
    edges (e.g., resolving `external_references` DOIs to in-corpus publication ids
    at persist time) is a tracked enhancement; until then this table stays empty
    and the directed citation_network renders with nodes but no edges.
    """
    __tablename__ = "citations"
    citing_publication_id: Mapped[int] = mapped_column(Integer, ForeignKey("publications.id", ondelete="CASCADE"), primary_key=True)
    cited_publication_id: Mapped[int] = mapped_column(Integer, ForeignKey("publications.id", ondelete="CASCADE"), primary_key=True)
    citing_publication: Mapped["Publication"] = relationship(foreign_keys=[citing_publication_id], back_populates="outgoing_citations")
    cited_publication: Mapped["Publication"] = relationship(foreign_keys=[cited_publication_id], back_populates="incoming_citations")
