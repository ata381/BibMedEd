from datetime import datetime
from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from bibmeded.database import Base

REVIEWER_LABEL_MAX_LENGTH = 64
RUN_ID_LENGTH = 36
SCREENING_DECISION_SOURCES = ("toggle", "bulk_exclude", "sample_seed")


class ScreeningDecision(Base):
    """One change to a publication's screening state, appended in the same
    transaction as the change and never updated afterwards.

    The ``previous_*`` columns snapshot the state the decision replaced, so the
    log stays readable even where earlier history predates the table.
    """

    __tablename__ = "screening_decisions"
    __table_args__ = (
        CheckConstraint(
            "screening_stage IS NULL OR screening_stage IN ('title_abstract', 'full_text')",
            name="ck_screening_decisions_screening_stage",
        ),
        CheckConstraint(
            "previous_screening_stage IS NULL OR previous_screening_stage IN ('title_abstract', 'full_text')",
            name="ck_screening_decisions_previous_screening_stage",
        ),
        CheckConstraint(
            "source IN ({})".format(", ".join(f"'{source}'" for source in SCREENING_DECISION_SOURCES)),
            name="ck_screening_decisions_source",
        ),
        # Leading project_id also serves the plain per-project lookups and the
        # project FK, so there is no separate single-column index on it.
        Index("ix_screening_decisions_project_id_run_id", "project_id", "run_id"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("search_projects.id", ondelete="CASCADE"))
    publication_id: Mapped[int] = mapped_column(ForeignKey("publications.id", ondelete="CASCADE"), index=True)
    # Always written as UTC. SQLite returns it without tzinfo, so readers treat a
    # naive value as UTC rather than local time.
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Free-text label from the X-Reviewer header: BibMedEd has no accounts, so
    # this is whatever the client says and NULL when it says nothing.
    reviewer: Mapped[str | None] = mapped_column(String(REVIEWER_LABEL_MAX_LENGTH), nullable=True)
    source: Mapped[str] = mapped_column(String(20))
    # One uuid4 per bulk request, shared by its decision rows and its
    # methodology step; NULL for single-record decisions.
    run_id: Mapped[str | None] = mapped_column(String(RUN_ID_LENGTH), nullable=True)
    criteria: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    previous_excluded: Mapped[bool] = mapped_column(Boolean)
    previous_exclusion_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    previous_screening_stage: Mapped[str | None] = mapped_column(String(20), nullable=True)
    excluded: Mapped[bool] = mapped_column(Boolean)
    exclusion_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    screening_stage: Mapped[str | None] = mapped_column(String(20), nullable=True)
    publication: Mapped["Publication"] = relationship()
