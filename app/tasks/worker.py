import json
import random
from typing import Any
from uuid import UUID

import requests
from celery import Task

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.tiny_logger import log_pack
from app.models.job import JobStatus
from app.services import job_service
from worker.celery_app import celery_app

settings = get_settings()


def _execute_data_processing(payload: dict[str, Any]) -> dict[str, Any]:
    records = payload.get("records")
    if records is None:
        raise ValueError("payload.records is required for data_processing")

    if isinstance(records, str):
        records = json.loads(records)
    if not isinstance(records, list):
        raise ValueError("records must be a list of objects")

    cleaned: list[dict[str, Any]] = []
    for row in records:
        if not isinstance(row, dict):
            continue
        normalized = {str(k).strip().lower(): v for k, v in row.items() if k is not None}
        cleaned.append(normalized)

    stats = {
        "input_count": len(records),
        "cleaned_count": len(cleaned),
        "keys_seen": sorted({k for row in cleaned for k in row.keys()}),
    }
    return {"cleaned_data": cleaned, "stats": stats}


def _execute_api_aggregation(payload: dict[str, Any]) -> dict[str, Any]:
    urls = payload.get("urls")
    if not urls or not isinstance(urls, list):
        raise ValueError("payload.urls must be a non-empty list")

    timeout = payload.get("timeout_seconds", 5)
    aggregated = []
    errors = []
    for url in urls:
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            aggregated.append({"url": url, "data": response.json()})
        except Exception as exc:  # noqa: BLE001
            errors.append({"url": url, "error": str(exc)})

    if errors and not aggregated:
        raise RuntimeError(f"all upstream API calls failed: {errors}")
    return {"responses": aggregated, "errors": errors, "count": len(aggregated)}


def _execute_computation_task(payload: dict[str, Any]) -> dict[str, Any]:
    iterations = int(payload.get("iterations", 500000))
    failure_rate = float(payload.get("failure_rate", 0.0))

    if random.random() < failure_rate:
        raise RuntimeError("simulated computation failure")

    # Intentionally CPU-heavy loop to model long-running compute tasks.
    total = 0
    for i in range(iterations):
        total += (i * i) % 97

    return {"iterations": iterations, "computed_value": total}


def _execute_job(job_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    if job_type == "data_processing":
        return _execute_data_processing(payload)
    if job_type == "api_aggregation":
        return _execute_api_aggregation(payload)
    if job_type == "computation_task":
        return _execute_computation_task(payload)
    raise ValueError(f"unsupported job type: {job_type}")


@celery_app.task(bind=True, name="app.tasks.worker.process_job")
def process_job(self: Task, job_id: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        parsed_job_id = UUID(job_id)
        job = job_service.get_job(db, parsed_job_id)
        if not job:
            raise ValueError(f"job not found: {job_id}")

        log_pack("job_started", job_id=job_id, task_type=job.type)
        job_service.push_job_log(
            db,
            job_id=job.id,
            event="job_started",
            level="INFO",
            msg="Job started",
            extra_blob={"task_type": job.type},
        )
        job_service.mark_job_running(db, job)
        result = _execute_job(job.type, job.payload)
        job_service.mark_job_completed(db, job, result)
        job = job_service.get_job(db, parsed_job_id)
        log_pack("job_completed", job_id=job_id, task_type=job.type, took_ms=job.took_ms)
        job_service.push_job_log(
            db,
            job_id=job.id,
            event="job_completed",
            level="INFO",
            msg="Job completed",
            extra_blob={"task_type": job.type, "took_ms": job.took_ms},
        )
        return {"job_id": job_id, "status": JobStatus.completed.value}
    except Exception as exc:  # noqa: BLE001
        parsed = UUID(job_id)
        job = job_service.get_job(db, parsed)
        if job is None:
            raise

        job = job_service.increment_retry_count(db, job)
        log_pack("job_error", job_id=job_id, task_type=job.type, error=str(exc), retry_count=job.retry_count)
        job_service.push_job_log(
            db,
            job_id=job.id,
            event="job_error",
            level="ERROR",
            msg="Job execution raised an error",
            extra_blob={"error": str(exc), "retry_count": job.retry_count},
        )
        if job.retry_count <= job.max_retries:
            job_service.mark_job_retrying(db, job, str(exc))
            countdown = settings.celery_retry_backoff_base_seconds ** job.retry_count
            job_service.push_job_log(
                db,
                job_id=job.id,
                event="job_retrying",
                level="WARNING",
                msg="Job scheduled for retry",
                extra_blob={"countdown_sec": countdown, "retry_count": job.retry_count},
            )
            raise self.retry(exc=exc, countdown=countdown, max_retries=job.max_retries)

        job_service.mark_job_failed(db, job, str(exc))
        log_pack("job_failed", job_id=job_id, task_type=job.type, error=str(exc), retries=job.retry_count)
        job_service.push_job_log(
            db,
            job_id=job.id,
            event="job_failed",
            level="ERROR",
            msg="Job failed after retries",
            extra_blob={"error": str(exc), "retry_count": job.retry_count},
        )
        return {"job_id": job_id, "status": JobStatus.failed.value, "error": str(exc)}
    finally:
        db.close()
