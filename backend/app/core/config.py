from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    postgres_user: str = Field(min_length=1)
    postgres_password: SecretStr = Field(min_length=1)
    postgres_db: str = Field(min_length=1)
    postgres_host: str = "localhost"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    redis_url: SecretStr
    cors_origins: list[str] = []
    jwt_secret: SecretStr | None = None
    jwt_issuer: str = "cinematch"
    jwt_audience: str = "cinematch-api"
    access_token_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_days: int = Field(default=7, ge=1, le=30)

    worker_max_retries: int = Field(default=5, ge=0)
    worker_retry_base_seconds: float = Field(default=2, gt=0)
    worker_retry_max_seconds: float = Field(default=300, gt=0)
    worker_claim_idle_ms: int = Field(default=60000, ge=100)
    worker_health_port: int = Field(default=9101, ge=1, le=65535)
    recommendation_batch_seconds: float = Field(default=5, ge=0, le=3600)
    recommendation_cache_ttl: int = Field(default=300, ge=1, le=86400)
    recommendation_top_n: int = Field(default=10, ge=1, le=100)
    recommendation_lease_seconds: int = Field(default=300, ge=10)

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg", username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host, port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
