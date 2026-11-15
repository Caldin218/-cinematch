from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router
from app.core.config import Settings, get_settings
from app.core.database import create_database_engine, get_session_factory
from app.core.health import HealthService
from app.core.logging import configure_logging
from app.core.redis import create_redis_client


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        engine = create_database_engine(config)
        redis = create_redis_client(config)
        app.state.session_factory = get_session_factory(engine)
        app.state.health_service = HealthService(engine, redis)
        try:
            yield
        finally:
            redis.close()
            engine.dispose()

    app = FastAPI(title="CineMatch API", version="0.1.0", lifespan=lifespan)
    if config.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=config.cors_origins,
                           allow_methods=["GET"], allow_headers=["Content-Type"])
    app.include_router(router)
    return app


app = create_app()
