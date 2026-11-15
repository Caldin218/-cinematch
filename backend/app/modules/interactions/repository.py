from collections.abc import Sequence
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Movie, MovieView, Rating, User, UserFavorite, Watchlist
from app.modules.interactions.schemas import InteractionPage

Collection = Literal["favorites", "watchlist"]


class InteractionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_user(self, user_id: UUID) -> User | None:
        return await self.session.scalar(select(User).where(User.id == user_id)
            .with_for_update().execution_options(populate_existing=True))

    async def active_movie(self, movie_id: int) -> Movie | None:
        # SHARE blocks catalog soft deletion until this transaction commits.
        return await self.session.scalar(select(Movie).where(Movie.id == movie_id, Movie.is_active)
            .with_for_update(read=True))

    async def view_by_request(self, user_id: UUID, request_id: UUID) -> MovieView | None:
        return await self.session.scalar(select(MovieView).where(
            MovieView.user_id == user_id, MovieView.request_id == request_id))

    async def add_view(self, user_id: UUID, movie_id: int, request_id: UUID) -> MovieView:
        return (await self.session.scalars(insert(MovieView).values(user_id=user_id, movie_id=movie_id,
            request_id=request_id, viewed_at=func.clock_timestamp()).returning(MovieView))).one()

    async def add_rating(self, user_id: UUID, movie_id: int, value: Decimal) -> Rating | None:
        return await self.session.scalar(insert(Rating).values(user_id=user_id, movie_id=movie_id, value=value,
            # Stable statement time keeps the two initial timestamps identical.
            created_at=func.statement_timestamp(), updated_at=func.statement_timestamp()).on_conflict_do_nothing(
                index_elements=[Rating.user_id, Rating.movie_id]).returning(Rating))

    async def rating(self, user_id: UUID, movie_id: int) -> Rating | None:
        return await self.session.scalar(select(Rating).where(Rating.user_id == user_id, Rating.movie_id == movie_id))

    async def collection_add(self, kind: Collection, user_id: UUID, movie_id: int) -> bool:
        model = UserFavorite if kind == "favorites" else Watchlist
        result = await self.session.scalar(insert(model).values(user_id=user_id, movie_id=movie_id,
            created_at=func.clock_timestamp()).on_conflict_do_nothing(
                index_elements=[model.user_id, model.movie_id]).returning(model.movie_id))
        return result is not None

    async def collection_remove(self, kind: Collection, user_id: UUID, movie_id: int) -> bool:
        model = UserFavorite if kind == "favorites" else Watchlist
        result = await self.session.scalar(delete(model).where(model.user_id == user_id, model.movie_id == movie_id)
            .returning(model.movie_id))
        return result is not None

    async def history(self, user_id: UUID, page: InteractionPage) -> tuple[Sequence[Row[Any]], int]:
        views = select(MovieView.movie_id, func.min(MovieView.viewed_at).label("first_viewed_at"),
            func.max(MovieView.viewed_at).label("last_viewed_at"), func.count().label("view_count")).where(
                MovieView.user_id == user_id).group_by(MovieView.movie_id).subquery()
        total = await self.session.scalar(select(func.count()).select_from(views))
        rows = (await self.session.execute(select(views.c.movie_id, Movie.title, Movie.is_active,
            views.c.first_viewed_at, views.c.last_viewed_at, views.c.view_count).join(Movie, Movie.id == views.c.movie_id)
            .order_by(views.c.last_viewed_at.desc(), views.c.movie_id).offset(page.offset).limit(page.page_size))).all()
        return rows, int(total or 0)

    async def collection(self, kind: Collection, user_id: UUID, page: InteractionPage) -> tuple[Sequence[Row[Any]], int]:
        model = UserFavorite if kind == "favorites" else Watchlist
        total = await self.session.scalar(select(func.count()).select_from(model).where(model.user_id == user_id))
        rows = (await self.session.execute(select(model.movie_id, Movie.title, Movie.is_active,
            model.created_at.label("added_at")).join(Movie, Movie.id == model.movie_id).where(model.user_id == user_id)
            .order_by(model.created_at.desc(), model.movie_id).offset(page.offset).limit(page.page_size))).all()
        return rows, int(total or 0)
