from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CourseBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    price: Decimal = Field(ge=0)
    status: str = Field(pattern="^(draft|published|archived)$")
    author_id: int | None = None


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, pattern="^(draft|published|archived)$")


class CourseRead(CourseBase):
    id: int
    avg_rating: Decimal
    reviews_count: int
    enrollments_count: int
    total_revenue: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
