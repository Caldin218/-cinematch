from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import Page
from app.core.errors import ApplicationError
from app.events.schema import new_event
from app.models import User
from app.modules.interactions.repository import Collection, InteractionRepository
from app.modules.interactions.schemas import (
    CollectionRead,
    HistoryRead,
    InteractionPage,
    RatingInput,
    RatingRead,
    RatingValue,
    ViewInput,
    ViewRead,
)


class InteractionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = InteractionRepository(session)

    @asynccontextmanager
    async def write(self, user_id: UUID) -> AsyncIterator[User]:
        try:
            # One durable per-user event sequence; also serializes retries and collection toggles.
            user = await self.repo.lock_user(user_id)
            if user is None or user.status != "active":
                raise ApplicationError("invalid_access_token", "Invalid or expired access token", 401)
            yield user
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def require_movie(self, movie_id: int) -> None:
        if await self.repo.active_movie(movie_id) is None:
            raise ApplicationError("movie_not_found", "Movie not found", 404)

    def record(self, user: User, movie_id: int, event_type: str, **payload: object) -> None:
        user.interaction_version += 1
        self.session.add(new_event(event_type=event_type, aggregate_type="user_interactions",
            aggregate_id=str(user.id), aggregate_version=user.interaction_version,
            user_id=user.id,
            payload={"user_id": str(user.id), "movie_id": movie_id, **payload}))

    async def view(self, user_id: UUID, data: ViewInput) -> ViewRead:
        async with self.write(user_id) as user:
            existing = await self.repo.view_by_request(user_id, data.request_id)
            if existing is not None:
                if existing.movie_id != data.movie_id:
                    raise ApplicationError("view_request_conflict", "Request ID already used for another movie", 409)
                result = ViewRead.model_validate(existing)
            else:
                await self.require_movie(data.movie_id)
                row = await self.repo.add_view(user_id, data.movie_id, data.request_id)
                self.record(user, data.movie_id, "movie.viewed", request_id=str(data.request_id), view_id=row.id)
                result = ViewRead.model_validate(row)
        return result

    async def create_rating(self, user_id: UUID, data: RatingInput) -> RatingRead:
        async with self.write(user_id) as user:
            await self.require_movie(data.movie_id)
            row = await self.repo.add_rating(user_id, data.movie_id, data.value)
            if row is None:
                raise ApplicationError("rating_exists", "Rating already exists; use PUT to update", 409)
            self.record(user, data.movie_id, "movie.rated", value=format(data.value, ".2f"))
            result = RatingRead.model_validate(row)
        return result

    async def update_rating(self, user_id: UUID, movie_id: int, data: RatingValue) -> RatingRead:
        async with self.write(user_id) as user:
            await self.require_movie(movie_id)
            row = await self.repo.rating(user_id, movie_id)
            if row is None:
                raise ApplicationError("rating_not_found", "Rating not found", 404)
            if row.value != data.value:
                old = row.value
                row.value = data.value
                row.updated_at = func.clock_timestamp()
                await self.session.flush()
                await self.session.refresh(row)
                self.record(user, movie_id, "movie.rated", value=format(data.value, ".2f"), previous_value=format(old, ".2f"))
            result = RatingRead.model_validate(row)
        return result

    async def change_collection(self, user_id: UUID, movie_id: int, kind: Collection, add: bool) -> None:
        async with self.write(user_id) as user:
            if add:
                await self.require_movie(movie_id)
                changed = await self.repo.collection_add(kind, user_id, movie_id)
            else:
                # Allow removal of a retained association even after a movie is deactivated.
                changed = await self.repo.collection_remove(kind, user_id, movie_id)
            if changed:
                self.record(user, movie_id, ("movie.favorite" if kind == "favorites" else "interaction.watchlist") + ("_added" if add else "_removed"))

    async def history(self, user_id: UUID, page: InteractionPage) -> Page[HistoryRead]:
        rows, total = await self.repo.history(user_id, page)
        return Page(items=[HistoryRead.model_validate(dict(row._mapping)) for row in rows],
            total=total, page=page.page, page_size=page.page_size)

    async def collection(self, user_id: UUID, kind: Collection, page: InteractionPage) -> Page[CollectionRead]:
        rows, total = await self.repo.collection(kind, user_id, page)
        return Page(items=[CollectionRead.model_validate(dict(row._mapping)) for row in rows],
            total=total, page=page.page, page_size=page.page_size)

    async def movie_state(self, user_id: UUID, movie_id: int):
        await self.require_movie(movie_id)
        return await self.repo.movie_state(user_id, movie_id)
