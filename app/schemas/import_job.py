from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ImportJobCreate(BaseModel):
    job_type: str = Field(min_length=1, max_length=50)
    params: dict[str, Any] | None = None
    total_records: int | None = Field(default=None, ge=0)


class ImportJobRead(BaseModel):
    id: int
    job_type: str
    status: str
    params: dict[str, Any] | None
    total_records: int | None
    processed_records: int | None
    errors_count: int | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class ImportJobErrorRead(BaseModel):
    id: int
    job_id: int
    row_number: int | None
    error_message: str
    payload: dict[str, Any] | None
    created_at: datetime

    class Config:
        from_attributes = True
