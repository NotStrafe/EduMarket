from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.api.deps import get_db
from app.schemas import ReviewCreate, ReviewRead

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("", response_model=ReviewRead, status_code=status.HTTP_201_CREATED)
async def create_review(payload: ReviewCreate, db: AsyncSession = Depends(get_db)) -> ReviewRead:
    review = models.Review(**payload.model_dump())
    db.add(review)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Review already exists or invalid references")
    await db.refresh(review)
    return review


@router.get("", response_model=list[ReviewRead])
async def list_reviews(db: AsyncSession = Depends(get_db)) -> list[ReviewRead]:
    result = await db.execute(select(models.Review))
    return result.scalars().all()
