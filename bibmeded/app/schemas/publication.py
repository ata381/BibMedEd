from pydantic import BaseModel

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
    journal_name: str | None = None
    authors: list[AuthorResponse] = []
    model_config = {"from_attributes": True}

class PublicationListResponse(BaseModel):
    total: int
    excluded_count: int = 0
    items: list[PublicationResponse]
