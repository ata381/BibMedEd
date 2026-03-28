from datetime import date, datetime
from pydantic import BaseModel, field_validator, model_validator

class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    date_range_start: date | None = None
    date_range_end: date | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Project name cannot be blank")
        return v

    @model_validator(mode="after")
    def dates_in_order(self):
        if self.date_range_start and self.date_range_end and self.date_range_start > self.date_range_end:
            raise ValueError("date_range_start must be before date_range_end")
        return self

class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    date_range_start: date | None = None
    date_range_end: date | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Project name cannot be blank")
        return v

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
