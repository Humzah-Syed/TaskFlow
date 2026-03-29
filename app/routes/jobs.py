from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.job import JobStatus
from app.schemas.job import (
    JobCreateRequest,
    JobCreateResponse,
    JobListItem,
    JobListResponse,
    JobLogItem,
    JobLogsResponse,
    JobResultResponse,
    JobStatusResponse,
)
from app.services import job_service
from app.tasks.worker import process_job

router = APIRouter(prefix="/jobs", tags=["jobs"])
settings = get_settings()


@router.post("", response_model=JobCreateResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_job(request: JobCreateRequest, db: Session = Depends(get_db)) -> JobCreateResponse:
    job = job_service.create_job(
        db,
        job_type=request.type,
        payload=request.payload,
        max_retries=settings.celery_max_retries,
    )
    process_job.delay(str(job.id))
    return JobCreateResponse(job_id=job.id, status=JobStatus(job.status))


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: UUID, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return JobStatusResponse(
        job_id=job.id,
        type=job.type,
        status=JobStatus(job.status),
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("/{job_id}/result", response_model=JobResultResponse)
def get_job_result(job_id: UUID, db: Session = Depends(get_db)) -> JobResultResponse:
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if job.status in {JobStatus.pending.value, JobStatus.running.value, JobStatus.retrying.value}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job is not completed yet",
        )

    return JobResultResponse(
        job_id=job.id,
        status=JobStatus(job.status),
        result=job.result,
        error_message=job.error_message,
    )


@router.get("", response_model=JobListResponse)
def list_jobs(
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=1000),
) -> JobListResponse:
    jobs = job_service.list_jobs(db, limit=limit)
    return JobListResponse(
        jobs=[
            JobListItem(
                job_id=job.id,
                type=job.type,
                status=JobStatus(job.status),
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
            for job in jobs
        ]
    )


@router.get("/{job_id}/logs", response_model=JobLogsResponse)
def get_job_logs(
    job_id: UUID,
    db: Session = Depends(get_db),
    limit: int = Query(200, ge=1, le=1000),
) -> JobLogsResponse:
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    little_logs = job_service.get_job_logs(db, job_id, limit=limit)
    return JobLogsResponse(
        job_id=job_id,
        logs=[
            JobLogItem(
                event=tiny.event,
                level=tiny.level,
                msg=tiny.msg,
                extra_blob=tiny.extra_blob,
                created_at=tiny.created_at,
            )
            for tiny in little_logs
        ],
    )
