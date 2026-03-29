from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import Base, engine
from app.models import job as _job_models  # noqa: F401 — registers models on metadata
from app.routes.jobs import router as jobs_router
from app.routes.metrics import router as metrics_router

settings = get_settings()

app = FastAPI(title=settings.app_name, version="1.0.0")


@app.on_event("startup")
def on_startup() -> None:
    # lazy: create tables on startup. real deploy would use alembic or whatever
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(jobs_router, prefix=settings.api_prefix)
app.include_router(metrics_router, prefix=settings.api_prefix)
