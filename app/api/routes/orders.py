from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.api.deps import get_db
from app.schemas import OrderCreate, OrderRead, PaymentCreate, PaymentRead

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(payload: OrderCreate, db: AsyncSession = Depends(get_db)) -> OrderRead:
    if not payload.items:
        raise HTTPException(status_code=400, detail="Order must contain at least one item")

    order = models.Order(user_id=payload.user_id, status="pending", total_amount=Decimal("0"))
    db.add(order)
    await db.flush()

    total = Decimal("0")
    for item in payload.items:
        course = await db.get(models.Course, item.course_id)
        if not course:
            await db.rollback()
            raise HTTPException(status_code=404, detail=f"Course {item.course_id} not found")
        total += course.price * item.quantity
        db.add(
            models.OrderItem(
                order_id=order.id,
                course_id=course.id,
                quantity=item.quantity,
                price=course.price,
            )
        )

    order.total_amount = total
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Failed to create order")
    await db.refresh(order)
    return order


@router.post("/payments", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
async def create_payment(payload: PaymentCreate, db: AsyncSession = Depends(get_db)) -> PaymentRead:
    order = await db.get(models.Order, payload.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    payment = models.Payment(
        order_id=payload.order_id,
        amount=payload.amount,
        status="paid",
        provider=payload.provider,
        transaction_id=payload.transaction_id,
        paid_at=datetime.utcnow(),
    )
    db.add(payment)

    order.status = "paid"
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Failed to create payment")
    await db.refresh(payment)
    return payment


@router.get("", response_model=list[OrderRead])
async def list_orders(db: AsyncSession = Depends(get_db)) -> list[OrderRead]:
    result = await db.execute(select(models.Order))
    return result.scalars().all()
