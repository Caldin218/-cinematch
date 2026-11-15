from collections.abc import Sequence
from typing import Any
from sqlalchemy.engine import Row
from sqlalchemy.sql import Select
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Movie, Genre, MovieGenre, Rating, MovieView
from app.modules.movies.schemas import CatalogQuery

class MovieRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def query(self) -> Select:
        ratings = select(Rating.movie_id, func.avg(Rating.value).label("average_rating"),
                         func.count().label("rating_count")).group_by(Rating.movie_id).subquery()
        views = select(MovieView.movie_id, func.count().label("popularity")).group_by(MovieView.movie_id).subquery()
        return select(Movie, ratings.c.average_rating, func.coalesce(ratings.c.rating_count, 0).label("rating_count"),
                      func.coalesce(views.c.popularity, 0).label("popularity")).outerjoin(
            ratings, ratings.c.movie_id == Movie.id).outerjoin(views, views.c.movie_id == Movie.id).where(Movie.is_active)

    async def listing(self, options: CatalogQuery) -> tuple[Sequence[Row[Any]], int]:
        stmt = self.query()
        if options.q is not None:
            prefix = options.q.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            stmt = stmt.where(func.lower(Movie.title).like(prefix + "%", escape="\\"))
        if options.genre_id is not None:
            stmt = stmt.where(select(MovieGenre.movie_id).where(MovieGenre.movie_id == Movie.id,
                MovieGenre.genre_id == options.genre_id).exists())
        if options.release_year is not None:
            stmt = stmt.where(Movie.release_year == options.release_year)
        average = stmt.selected_columns.average_rating
        if options.min_rating is not None:
            stmt = stmt.where(average >= options.min_rating)
        if options.max_rating is not None:
            stmt = stmt.where(average <= options.max_rating)
        total = await self.session.scalar(select(func.count()).select_from(stmt.subquery()))
        order = {"popularity": stmt.selected_columns.popularity, "rating": average,
                 "release_year": Movie.release_year}[options.sort]
        rows = (await self.session.execute(stmt.order_by(order.desc().nullslast(), Movie.id)
            .offset(options.offset).limit(options.page_size))).all()
        return rows, int(total or 0)

    async def detail(self, movie_id: int) -> Row[Any] | None:
        return (await self.session.execute(self.query().where(Movie.id == movie_id))).first()

    async def locked(self, movie_id: int) -> Movie | None:
        return await self.session.scalar(select(Movie).where(Movie.id == movie_id, Movie.is_active).with_for_update())

    async def genres(self, ids: list[int]) -> dict[int, list[Genre]]:
        rows = (await self.session.execute(select(MovieGenre.movie_id, Genre).join(Genre)
            .where(MovieGenre.movie_id.in_(ids)).order_by(Genre.name, Genre.id))).all() if ids else []
        result = {key: [] for key in ids}
        for movie_id, genre in rows:
            result[movie_id].append(genre)
        return result

    async def genre_ids(self, ids: list[int]) -> set[int]:
        # Lock referenced genres until commit to serialize deletion with assignment.
        return set((await self.session.scalars(select(Genre.id).where(Genre.id.in_(ids))
            .order_by(Genre.id).with_for_update())).all()) if ids else set()

    async def replace_genres(self, movie_id: int, ids: list[int]) -> None:
        await self.session.execute(delete(MovieGenre).where(MovieGenre.movie_id == movie_id))
        self.session.add_all([MovieGenre(movie_id=movie_id, genre_id=key) for key in ids])
