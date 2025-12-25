from datetime import datetime

from pydantic import BaseModel, Field


class EnrollmentCreate(BaseModel):
    user_id: int
    course_id: int
    status: str = Field(default="active", pattern="^(active|completed|cancelled)$")
    started_at: datetime | None = None
    completed_at: datetime | None = None


class EnrollmentRead(BaseModel):
    id: int
    user_id: int
    course_id: int
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True
