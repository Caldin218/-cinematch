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
from app.core.runtime import create_async_resources
from app.core.errors import install_handlers
from app.core.correlation import CorrelationMiddleware
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.movies.router import router as movies_router
from app.modules.genres.router import router as genres_router
from app.modules.interactions.router import router as interactions_router


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        engine = create_database_engine(config)
        redis = create_redis_client(config)
        app.state.session_factory = get_session_factory(engine)
        app.state.health_service = HealthService(engine, redis)
        async_engine = None
        async_redis = None
        try:
            async_engine, async_redis, sessions = create_async_resources(config)
            app.state.async_sessions = sessions
            app.state.async_redis = async_redis
            yield
        finally:
            try:
                if async_redis is not None:
                    await async_redis.aclose()
            finally:
                try:
                    if async_engine is not None:
                        await async_engine.dispose()
                finally:
                    try:
                        redis.close()
                    finally:
                        engine.dispose()

    app = FastAPI(title="CineMatch API", version="0.1.0", lifespan=lifespan)
    app.state.settings = config
    if config.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=config.cors_origins,
                           allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                           allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
                           expose_headers=["X-Request-ID"])
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(movies_router, prefix="/api/v1")
    app.include_router(genres_router, prefix="/api/v1")
    app.include_router(interactions_router, prefix="/api/v1")
    install_handlers(app)
    app.add_middleware(CorrelationMiddleware)
    app.include_router(router)
    app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
