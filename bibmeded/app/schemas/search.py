from pydantic import BaseModel

class SearchRequest(BaseModel):
    query_string: str
    database: str = "pubmed"
    source: str = "pubmed"
    year_start: str | None = None
    year_end: str | None = None
    max_results: int = 2000

class SearchStatusResponse(BaseModel):
    query_id: int
    status: str
    result_count: int | None
    raw_result_count: int | None = None
    duplicate_count: int | None = None
    progress: float | None = None
    model_config = {"from_attributes": True}
