from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings

from .cache import RecommendationCache
from .repository import RecommendationRepository
from .schemas import Item, RecommendationRead, RefreshRead


class RecommendationService:
    def __init__(self, session: AsyncSession, redis: Redis, settings: Settings):
        self.repo = RecommendationRepository(session)
        self.cache = RecommendationCache(redis, settings.recommendation_cache_ttl)
        self.settings = settings

    async def refresh(self, user_id: UUID) -> RefreshRead:
        due = await self.repo.schedule(user_id, self.settings.recommendation_batch_seconds)
        assert due is not None
        await self.cache.invalidate(user_id)
        return RefreshRead(scheduled_for=due)

    async def get(self, user_id: UUID, n: int | None = None) -> RecommendationRead:
        n = min(n or self.settings.recommendation_top_n, self.settings.recommendation_top_n)
        job = await self.repo.job(user_id)
        if job is None:
            await self.repo.schedule(user_id, self.settings.recommendation_batch_seconds, only_if_missing=True)
        if job is None or job.generated_at is None:
            candidates = await self.repo.eligible(user_id, limit=n)
            return RecommendationRead(items=[Item(movie_id=m, rank=i, method="catalog_fallback")
                for i, m in enumerate(candidates, 1)], algorithm_version="catalog-fallback-v1",
                status="unavailable", fallback="Recommendations pending; showing unrated catalog movies.")

        dirty = job.revision != job.completed_revision
        # Checking the durable revision makes event invalidation safe even when Redis is down.
        result = None if dirty else await self.cache.get(user_id, job.completed_revision)
        if result is None:
            rows = await self.repo.results(user_id, job.generated_at)
            result = RecommendationRead(items=[Item(movie_id=r.movie_id, rank=r.rank, method=r.method,
                ranking_score=r.ranking_score,
                predicted_rating=r.predicted_rating, popularity_score=r.popularity_score) for r in rows],
                generated_at=job.generated_at, source_cutoff=job.source_cutoff,
                algorithm_version=job.algorithm_version or "legacy-unknown", generation_seconds=job.generation_seconds,
                status="ready")
            if not dirty:
                await self.cache.put(user_id, job.completed_revision, result)

        # Always consult current interactions: events and calculations are eventually consistent.
        allowed = set(await self.repo.eligible(user_id, [item.movie_id for item in result.items]))
        result = result.model_copy(deep=True)
        result.items = [item for item in result.items if item.movie_id in allowed][:n]
        for rank, item in enumerate(result.items, 1):
            item.rank = rank
        if dirty:
            result.status = "stale"
            result.fallback = "Serving previous recommendations while refresh is pending."
        return result

