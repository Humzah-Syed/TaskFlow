from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.job import SystemMetricsResponse
from app.services import job_service

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", response_model=SystemMetricsResponse)
def get_system_metrics(db: Session = Depends(get_db)) -> SystemMetricsResponse:
    bits = job_service.grab_metrics(db)
    return SystemMetricsResponse(**bits)
