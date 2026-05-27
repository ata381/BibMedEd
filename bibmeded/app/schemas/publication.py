from typing import Literal

from pydantic import BaseModel, Field

# PRISMA 2020 exclusion-reason categories. `None` for the literal type means
# "no reason recorded" — equivalent to legacy excluded-without-reason rows.
ExclusionReason = Literal[
    "wrong_study_design",
    "wrong_population",
    "wrong_intervention",
    "wrong_outcome",
    "not_peer_reviewed",
    "non_english",
    "duplicate",
    "fulltext_unavailable",
    "other",
]


class AuthorResponse(BaseModel):
    id: int
    name: str
    orcid: str | None
    model_config = {"from_attributes": True}

class PublicationResponse(BaseModel):
    id: int
    pmid: str
    doi: str | None
    title: str
    abstract: str | None
    year: int | None
    publication_type: str | None
    citation_count: int | None
    excluded: bool = False
    exclusion_reason: ExclusionReason | None = None
    journal_name: str | None = None
    authors: list[AuthorResponse] = []
    model_config = {"from_attributes": True}

class PublicationListResponse(BaseModel):
    total: int
    excluded_count: int = 0
    items: list[PublicationResponse]


class BulkExcludeRequest(BaseModel):
    citation_threshold: int = Field(default=0, ge=0)
    # Reason recorded against every record bulk-excluded by this request. Defaults to
    # "other" so the methodology log can always report a reason breakdown.
    reason: ExclusionReason = "other"


class ToggleExcludeRequest(BaseModel):
    # Optional on include (the field is cleared when the record is re-included).
    reason: ExclusionReason | None = None
