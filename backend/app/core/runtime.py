"""Async request dependencies; services explicitly own transaction commits."""
from collections.abc import AsyncIterator
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker
from redis.asyncio import Redis
from app.core.config import Settings


def create_async_resources(settings: Settings) -> tuple[AsyncEngine, Redis, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"}, pool_timeout=3)
    redis = Redis.from_url(settings.redis_url.get_secret_value(), decode_responses=True,
                           socket_timeout=3, socket_connect_timeout=3)
    return engine, redis, async_sessionmaker(engine, expire_on_commit=False)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.async_sessions() as session:
        try:
            yield session
        finally:
            await session.rollback()


def get_redis(request: Request) -> Redis:
    return request.app.state.async_redis
