from typing import Literal, get_args

from pydantic import BaseModel, Field, field_validator, model_validator

from bibmeded.models.publication import NOT_RETRIEVED_REASON

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

# PRISMA 2020 screening stage an exclusion was made at: title/abstract screening
# of records, or full-text assessment of reports. Must match
# bibmeded.models.publication.SCREENING_STAGES and its CHECK constraint.
ScreeningStage = Literal["title_abstract", "full_text"]
DEFAULT_SCREENING_STAGE: ScreeningStage = "title_abstract"

_STAGE_DESCRIPTION = (
    "PRISMA 2020 screening stage of the exclusion: 'title_abstract' (records screened) "
    "or 'full_text' (reports assessed for eligibility). Omitted or null means 'full_text' "
    "for reason 'fulltext_unavailable' and 'title_abstract' otherwise; "
    "'fulltext_unavailable' with 'title_abstract' is rejected with 422."
)


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
    screening_stage: ScreeningStage | None = Field(
        default=None, description="Stage the record was excluded at; null while it is included."
    )
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


class _StagedExclusionRequest(BaseModel):
    """Stage rule shared by both exclude endpoints.

    Omitted or null → ``full_text`` for ``fulltext_unavailable`` (PRISMA 2020
    "Reports not retrieved" only exists at full text), ``title_abstract``
    otherwise. ``fulltext_unavailable`` with an explicit ``title_abstract`` is a
    contradiction and is rejected with 422 rather than silently re-staged.
    """

    reason: ExclusionReason | None = None
    screening_stage: ScreeningStage | None = Field(default=None, description=_STAGE_DESCRIPTION)

    @model_validator(mode="after")
    def _reject_unretrieved_title_abstract_exclusion(self):
        if self.reason == NOT_RETRIEVED_REASON and self.screening_stage == "title_abstract":
            raise ValueError(
                "reason 'fulltext_unavailable' records a report that could not be retrieved, which "
                "PRISMA 2020 counts at the full-text stage; use screening_stage 'full_text' or omit it"
            )
        return self

    @property
    def resolved_screening_stage(self) -> ScreeningStage:
        if self.screening_stage is not None:
            return self.screening_stage
        return "full_text" if self.reason == NOT_RETRIEVED_REASON else DEFAULT_SCREENING_STAGE


class BulkExcludeRequest(_StagedExclusionRequest):
    citation_threshold: int = Field(default=0, ge=0)
    # Reason recorded against every record bulk-excluded by this request. Defaults to
    # "other" so the methodology log can always report a reason breakdown.
    reason: ExclusionReason = "other"


class BulkExcludeResponse(BaseModel):
    excluded_count: int
    reason: ExclusionReason
    screening_stage: ScreeningStage


class ToggleExcludeRequest(_StagedExclusionRequest):
    """Both fields are ignored on re-include, which clears reason and stage."""


class ToggleExcludeResponse(BaseModel):
    id: int
    excluded: bool
    exclusion_reason: ExclusionReason | None
    screening_stage: ScreeningStage | None
