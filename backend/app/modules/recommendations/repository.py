from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Movie, Rating, Recommendation, RecommendationJob

from .scheduling import schedule_statement


class RecommendationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def job(self, user_id: UUID) -> RecommendationJob | None:
        return await self.session.get(RecommendationJob, user_id)

    async def schedule(self, user_id: UUID, seconds: float, *, only_if_missing: bool = False) -> datetime | None:
        statement = schedule_statement(user_id, seconds)
        if only_if_missing:
            from datetime import timedelta

            from sqlalchemy import func
            from sqlalchemy.dialects.postgresql import insert
            statement = insert(RecommendationJob).values(user_id=user_id,
                due_at=func.clock_timestamp() + timedelta(seconds=seconds)).on_conflict_do_nothing()
        result = await self.session.scalar(statement.returning(RecommendationJob.due_at))
        await self.session.commit()
        return result

    async def results(self, user_id: UUID, generated_at: datetime) -> list[Recommendation]:
        return list(await self.session.scalars(select(Recommendation).where(
            Recommendation.user_id == user_id, Recommendation.generated_at == generated_at
        ).order_by(Recommendation.rank)))

    async def eligible(self, user_id: UUID, movie_ids: list[int] | None = None, limit: int = 100) -> list[int]:
        rated = select(Rating.movie_id).where(Rating.user_id == user_id)
        statement = select(Movie.id).where(Movie.is_active, Movie.id.not_in(rated))
        if movie_ids is not None:
            statement = statement.where(Movie.id.in_(movie_ids))
        return list(await self.session.scalars(statement.order_by(Movie.id).limit(limit)))
