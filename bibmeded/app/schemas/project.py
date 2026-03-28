from datetime import date, datetime
from pydantic import BaseModel

class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    date_range_start: date | None = None
    date_range_end: date | None = None

class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    date_range_start: date | None = None
    date_range_end: date | None = None

class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None
    date_range_start: date | None
    date_range_end: date | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class ProjectListResponse(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: datetime
    publication_count: int = 0
    model_config = {"from_attributes": True}
