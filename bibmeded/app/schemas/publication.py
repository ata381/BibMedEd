from typing import Literal, get_args

from pydantic import BaseModel, Field, field_validator

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

    @field_validator("exclusion_reason", mode="before")
    @classmethod
    def _coerce_legacy_reason(cls, v):
        """Coerce DB rows with legacy / unknown exclusion_reason strings to 'other'
        so a row written before the Literal was introduced doesn't blow up the
        response serializer and silently drop the publication."""
        if v is None or v == "":
            return None
        if v in get_args(ExclusionReason):
            return v
        return "other"

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
