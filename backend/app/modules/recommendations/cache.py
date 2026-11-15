import logging
from uuid import UUID

from pydantic import ValidationError
from redis.exceptions import RedisError

from .schemas import CachedRecommendations, RecommendationRead

logger = logging.getLogger(__name__)


def cache_key(user_id: UUID) -> str:
    return f"recommendations:user:{user_id}"


class RecommendationCache:
    def __init__(self, redis, ttl):
        self.redis, self.ttl = redis, ttl

    async def get(self, user_id: UUID, revision: int) -> RecommendationRead | None:
        try:
            raw = await self.redis.get(cache_key(user_id))
            if raw is None:
                return None
            cached = CachedRecommendations.model_validate_json(raw)
            if cached.user_id == user_id and cached.revision == revision:
                return cached.result
            await self.invalidate(user_id)
        except (ValidationError, ValueError, TypeError):
            await self.invalidate(user_id)
        except RedisError:
            logger.warning("recommendation_cache_read_failed")
        return None

    async def put(self, user_id: UUID, revision: int, result: RecommendationRead) -> None:
        cached = CachedRecommendations(user_id=user_id, revision=revision, result=result)
        try:
            await self.redis.set(cache_key(user_id), cached.model_dump_json(), ex=self.ttl)
        except RedisError:
            logger.warning("recommendation_cache_write_failed")

    async def invalidate(self, user_id: UUID) -> None:
        try:
            await self.redis.delete(cache_key(user_id))
        except RedisError:
            logger.warning("recommendation_cache_delete_failed")
