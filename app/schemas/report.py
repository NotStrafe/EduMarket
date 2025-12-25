from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class TopCourseItem(BaseModel):
    course_id: int
    title: str
    revenue: Decimal
    orders_count: int
    payments_count: int


class UserActivityItem(BaseModel):
    user_id: int
    email: str
    enrollments_count: int
    lessons_completed: int
    payments_count: int


class SalesDynamicsItem(BaseModel):
    period_start: date
    revenue: Decimal
    orders_count: int
    payments_count: int
