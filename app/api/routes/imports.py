from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.api.deps import get_db
from app.db.session import SessionLocal
from app.schemas import ImportJobCreate, ImportJobErrorRead, ImportJobRead

router = APIRouter(prefix="/batch-import", tags=["batch-import"])


@router.post("", response_model=ImportJobRead, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_import(
    payload: ImportJobCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ImportJobRead:
    job = models.ImportJob(
        job_type=payload.job_type,
        status="pending",
        params=payload.params,
        total_records=payload.total_records or 100,
        processed_records=0,
        errors_count=0,
    )
    db.add(job)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Failed to create import job")
    await db.refresh(job)

    background_tasks.add_task(_process_job, job.id)
    return job


@router.get("", response_model=list[ImportJobRead])
async def list_jobs(db: AsyncSession = Depends(get_db)) -> list[ImportJobRead]:
    result = await db.execute(select(models.ImportJob).order_by(models.ImportJob.created_at.desc()))
    return result.scalars().all()


@router.get("/{job_id}", response_model=ImportJobRead)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)) -> ImportJobRead:
    job = await db.get(models.ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/errors", response_model=list[ImportJobErrorRead])
async def list_job_errors(job_id: int, db: AsyncSession = Depends(get_db)) -> list[ImportJobErrorRead]:
    job = await db.get(models.ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result = await db.execute(
        select(models.ImportJobError).where(models.ImportJobError.job_id == job_id).order_by(models.ImportJobError.id)
    )
    return result.scalars().all()


async def _process_job(job_id: int) -> None:
    async with SessionLocal() as session:
        job = await session.get(models.ImportJob, job_id)
        if not job:
            return
        now = datetime.now(timezone.utc)
        job.status = "processing"
        job.started_at = now
        await session.commit()

        total = job.total_records or 100
        errors: list[dict[str, Any]] = []

        # Симуляция ошибок: до 3 случайных ошибок
        error_count = min(3, max(0, total // 50))
        for idx in range(error_count):
            errors.append(
                {
                    "row_number": idx + 1,
                    "error_message": f"Sample error #{idx + 1}",
                    "payload": {"row": idx + 1},
                }
            )

        processed = total
        finished_at = now + timedelta(seconds=1)

        # Записываем ошибки, если есть
        for err in errors:
            session.add(
                models.ImportJobError(
                    job_id=job_id,
                    row_number=err["row_number"],
                    error_message=err["error_message"],
                    payload=err["payload"],
                )
            )

        job.status = "failed" if errors else "completed"
        job.processed_records = processed
        job.errors_count = len(errors)
        job.finished_at = finished_at
        await session.commit()

        # Обновить в БД число ошибок, если нужно
        if errors:
            await session.execute(
                update(models.ImportJob)
                .where(models.ImportJob.id == job_id)
                .values(errors_count=len(errors), processed_records=processed)
            )
            await session.commit()
