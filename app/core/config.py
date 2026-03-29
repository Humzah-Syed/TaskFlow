from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TaskFlow"
    api_prefix: str = "/api/v1"
    environment: str = "development"

    postgres_user: str = "taskflow"
    postgres_password: str = "taskflow"
    postgres_host: str = "localhost"
    # Default matches docker/docker-compose.yml host mapping (5433 -> container 5432).
    postgres_port: int = 5433
    postgres_db: str = "taskflow"

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    celery_max_retries: int = 3
    celery_retry_backoff_base_seconds: int = 2

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def celery_broker_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def celery_result_backend(self) -> str:
        return self.celery_broker_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
