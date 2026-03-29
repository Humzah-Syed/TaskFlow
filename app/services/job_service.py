from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.job import Job, JobLog, JobStatus


def create_job(db: Session, *, job_type: str, payload: dict, max_retries: int) -> Job:
    job = Job(type=job_type, payload=payload, status=JobStatus.pending.value, max_retries=max_retries)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: UUID) -> Job | None:
    return db.query(Job).filter(Job.id == job_id).first()


def list_jobs(db: Session, limit: int = 100) -> list[Job]:
    return db.query(Job).order_by(desc(Job.created_at)).limit(limit).all()


def mark_job_running(db: Session, job: Job) -> Job:
    job.status = JobStatus.running.value
    job.error_message = None
    job.started_at = datetime.now(timezone.utc)
    job.finished_at = None
    job.took_ms = None
    db.commit()
    db.refresh(job)
    return job


def mark_job_retrying(db: Session, job: Job, error_message: str) -> Job:
    job.status = JobStatus.retrying.value
    job.error_message = error_message
    db.commit()
    db.refresh(job)
    return job


def mark_job_completed(db: Session, job: Job, result: dict) -> Job:
    job.status = JobStatus.completed.value
    job.result = result
    job.error_message = None
    job.finished_at = datetime.now(timezone.utc)
    if job.started_at is not None:
        gap = job.finished_at - job.started_at
        job.took_ms = int(gap.total_seconds() * 1000)
    db.commit()
    db.refresh(job)
    return job


def mark_job_failed(db: Session, job: Job, error_message: str) -> Job:
    job.status = JobStatus.failed.value
    job.error_message = error_message
    job.finished_at = datetime.now(timezone.utc)
    if job.started_at is not None:
        gap = job.finished_at - job.started_at
        job.took_ms = int(gap.total_seconds() * 1000)
    db.commit()
    db.refresh(job)
    return job


def increment_retry_count(db: Session, job: Job) -> Job:
    job.retry_count += 1
    db.commit()
    db.refresh(job)
    return job


def push_job_log(
    db: Session,
    *,
    job_id: UUID,
    event: str,
    level: str,
    msg: str,
    extra_blob: dict | None = None,
) -> JobLog:
    tiny_log = JobLog(
        job_id=job_id,
        event=event,
        level=level,
        msg=msg,
        extra_blob=extra_blob,
    )
    db.add(tiny_log)
    db.commit()
    db.refresh(tiny_log)
    return tiny_log


def get_job_logs(db: Session, job_id: UUID, limit: int = 200) -> list[JobLog]:
    return (
        db.query(JobLog)
        .filter(JobLog.job_id == job_id)
        .order_by(desc(JobLog.created_at))
        .limit(limit)
        .all()
    )


def grab_metrics(db: Session) -> dict:
    ok_cnt = db.query(func.count(Job.id)).filter(Job.status == JobStatus.completed.value).scalar() or 0
    bad_cnt = db.query(func.count(Job.id)).filter(Job.status == JobStatus.failed.value).scalar() or 0
    avg_ms = db.query(func.avg(Job.took_ms)).filter(Job.took_ms.is_not(None)).scalar()
    all_retry = db.query(func.coalesce(func.sum(Job.retry_count), 0)).scalar() or 0
    total_done = ok_cnt + bad_cnt
    return {
        "total_jobs_processed": total_done,
        "success_count": ok_cnt,
        "failure_count": bad_cnt,
        "average_processing_time_ms": float(avg_ms) if avg_ms is not None else 0.0,
        "retry_count": int(all_retry),
    }
