from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.job import JobStatus


class JobCreateRequest(BaseModel):
    type: str = Field(..., examples=["data_processing", "api_aggregation", "computation_task"])
    payload: dict[str, Any]


class JobCreateResponse(BaseModel):
    job_id: UUID
    status: JobStatus


class JobStatusResponse(BaseModel):
    job_id: UUID
    type: str
    status: JobStatus
    retry_count: int
    max_retries: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class JobResultResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    result: dict[str, Any] | None = None
    error_message: str | None = None


class JobListItem(BaseModel):
    job_id: UUID
    type: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime


class JobListResponse(BaseModel):
    jobs: list[JobListItem]


class JobLogItem(BaseModel):
    event: str
    level: str
    msg: str
    extra_blob: dict[str, Any] | None
    created_at: datetime


class JobLogsResponse(BaseModel):
    job_id: UUID
    logs: list[JobLogItem]


class SystemMetricsResponse(BaseModel):
    total_jobs_processed: int
    success_count: int
    failure_count: int
    average_processing_time_ms: float
    retry_count: int
