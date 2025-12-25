from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas import SalesDynamicsItem, TopCourseItem, UserActivityItem

router = APIRouter(prefix="/reports", tags=["reports"])


def default_period(days: int) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    return now - timedelta(days=days), now


@router.get("/top-courses", response_model=list[TopCourseItem])
async def top_courses_by_revenue(
    db: AsyncSession = Depends(get_db),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
) -> list[TopCourseItem]:
    start_dt, end_dt = (start, end) if start and end else default_period(90)
    result = await db.execute(
        text(
            "SELECT * FROM fn_top_courses_by_revenue(:start_dt, :end_dt, :limit)"
        ),
        {"start_dt": start_dt, "end_dt": end_dt, "limit": limit},
    )
    return [TopCourseItem(**row._mapping) for row in result]


@router.get("/user-activity", response_model=list[UserActivityItem])
async def user_activity(
    db: AsyncSession = Depends(get_db),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
) -> list[UserActivityItem]:
    start_dt, end_dt = (start, end) if start and end else default_period(30)
    result = await db.execute(
        text("SELECT * FROM fn_user_activity(:start_dt, :end_dt)"),
        {"start_dt": start_dt, "end_dt": end_dt},
    )
    return [UserActivityItem(**row._mapping) for row in result]


@router.get("/sales-dynamics", response_model=list[SalesDynamicsItem])
async def sales_dynamics(
    db: AsyncSession = Depends(get_db),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
) -> list[SalesDynamicsItem]:
    start_dt, end_dt = (start, end) if start and end else default_period(180)
    result = await db.execute(
        text("SELECT * FROM fn_sales_dynamics(:start_dt, :end_dt)"),
        {"start_dt": start_dt, "end_dt": end_dt},
    )
    return [SalesDynamicsItem(**row._mapping) for row in result]
