import sys

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "taskflow_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    imports=("app.tasks.worker",),
)

# win + prefork was throwing PermissionError on semlocks for me — solo pool dodges that
if sys.platform == "win32":
    celery_app.conf.worker_pool = "solo"
