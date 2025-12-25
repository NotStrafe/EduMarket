from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class OrderItemCreate(BaseModel):
    course_id: int
    quantity: int = Field(default=1, ge=1)


class OrderCreate(BaseModel):
    user_id: int
    items: list[OrderItemCreate]


class OrderRead(BaseModel):
    id: int
    user_id: int
    status: str
    total_amount: Decimal
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentCreate(BaseModel):
    order_id: int
    amount: Decimal = Field(ge=0)
    provider: str | None = None
    transaction_id: str | None = None


class PaymentRead(BaseModel):
    id: int
    order_id: int
    amount: Decimal
    status: str
    provider: str | None
    transaction_id: str | None
    paid_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True
