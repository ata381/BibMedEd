from pydantic import BaseModel

class SearchRequest(BaseModel):
    query_string: str
    database: str = "pubmed"

class SearchStatusResponse(BaseModel):
    query_id: int
    status: str
    result_count: int | None
    raw_result_count: int | None = None
    duplicate_count: int | None = None
    progress: float | None = None
    model_config = {"from_attributes": True}
