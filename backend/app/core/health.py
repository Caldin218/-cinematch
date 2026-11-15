import logging
from typing import Literal

from pydantic import BaseModel
from redis import Redis
from sqlalchemy import Engine

from app.core.database import check_database
from app.core.redis import check_redis

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: Literal["ok", "ready", "not_ready"]
    checks: dict[str, Literal["up", "down"]] = {}


class HealthService:
    def __init__(self, engine: Engine, redis: Redis) -> None:
        self.engine = engine
        self.redis = redis

    def readiness(self) -> HealthResponse:
        checks: dict[str, Literal["up", "down"]] = {}
        for name, check, resource in (
            ("postgresql", check_database, self.engine),
            ("redis", check_redis, self.redis),
        ):
            try:
                check(resource)
                checks[name] = "up"
            except Exception:
                # Do not expose dependency exceptions or connection credentials.
                logger.warning("dependency_unavailable", extra={"dependency": name})
                checks[name] = "down"
        return HealthResponse(
            status="ready" if all(v == "up" for v in checks.values()) else "not_ready",
            checks=checks,
        )
