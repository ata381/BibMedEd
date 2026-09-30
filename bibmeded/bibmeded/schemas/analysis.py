from datetime import datetime
from pydantic import BaseModel
from typing import Any

class AnalysisRequest(BaseModel):
    analysis_type: str

class AnalysisResponse(BaseModel):
    id: int
    project_id: int
    analysis_type: str
    results: Any
    created_at: datetime
    model_config = {"from_attributes": True}
