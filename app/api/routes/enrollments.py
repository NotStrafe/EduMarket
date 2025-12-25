from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.api.deps import get_db
from app.schemas import EnrollmentCreate, EnrollmentRead

router = APIRouter(prefix="/enrollments", tags=["enrollments"])


@router.post("", response_model=EnrollmentRead, status_code=status.HTTP_201_CREATED)
async def create_enrollment(payload: EnrollmentCreate, db: AsyncSession = Depends(get_db)) -> EnrollmentRead:
    enrollment = models.Enrollment(**payload.model_dump())
    db.add(enrollment)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Enrollment already exists or invalid references")
    await db.refresh(enrollment)
    return enrollment


@router.get("", response_model=list[EnrollmentRead])
async def list_enrollments(db: AsyncSession = Depends(get_db)) -> list[EnrollmentRead]:
    result = await db.execute(select(models.Enrollment))
    return result.scalars().all()
