from typing import Literal

from pydantic import BaseModel, Field

AdapterSource = Literal["pubmed", "openalex", "crossref", "semanticscholar"]


class SearchRequest(BaseModel):
    query_string: str = Field(min_length=1, max_length=10_000)
    source: AdapterSource = "pubmed"
    year_start: str | None = None
    year_end: str | None = None
    max_results: int = Field(default=2000, ge=1, le=10_000)


class SearchStatusResponse(BaseModel):
    query_id: int
    status: str
    result_count: int | None
    raw_result_count: int | None = None
    duplicate_count: int | None = None
    progress: float | None = None
    model_config = {"from_attributes": True}
