from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import Page
from app.core.errors import ApplicationError
from app.events.schema import new_event
from app.models import Movie
from app.modules.movies.repository import MovieRepository
from app.modules.movies.schemas import CatalogQuery, MovieCreate, MovieRead, MovieUpdate


class MovieService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = MovieRepository(session)

    async def serialize(self, rows: Sequence[Row[Any]]) -> list[MovieRead]:
        genres = await self.repo.genres([row[0].id for row in rows])
        return [MovieRead.model_validate({**{name: getattr(row[0], name) for name in
            ("id", "title", "synopsis", "release_year", "runtime_minutes", "poster_url", "original_title", "trailer_youtube_id", "version")},
            "genres": genres[row[0].id], "average_rating": row[1], "rating_count": row[2], "popularity": row[3], "comment_count": row[4]}) for row in rows]

    async def listing(self, query: CatalogQuery, user_id: UUID | None = None) -> Page[MovieRead]:
        rows, total = await self.repo.listing(query, user_id)
        return Page(items=await self.serialize(rows), total=total, page=query.page, page_size=query.page_size)

    async def detail(self, movie_id: int) -> MovieRead:
        row = await self.repo.detail(movie_id)
        if row is None:
            raise ApplicationError("movie_not_found", "Movie not found", 404)
        return (await self.serialize([row]))[0]

    async def save(self, data: MovieCreate | MovieUpdate, movie_id: int | None = None) -> MovieRead:
        movie = await self.repo.locked(movie_id) if movie_id is not None else Movie()
        if movie is None:
            raise ApplicationError("movie_not_found", "Movie not found", 404)
        fields = data.model_dump(mode="json", exclude_unset=movie_id is not None)
        ids = fields.pop("genre_ids", None)
        if ids is not None and await self.repo.genre_ids(ids) != set(ids):
            raise ApplicationError("invalid_genres", "One or more genres do not exist", 422)
        for key, value in fields.items():
            setattr(movie, key, value)
        if movie_id is not None:
            movie.version += 1
        self.session.add(movie)
        await self.session.flush()
        if ids is not None:
            await self.repo.replace_genres(movie.id, ids)
        self.event(movie, "movie.created" if movie_id is None else "movie.updated")
        await self.session.commit()
        return await self.detail(movie.id)

    def event(self, movie: Movie, event_type: str) -> None:
        self.session.add(new_event(event_type=event_type, aggregate_type="movie", aggregate_id=str(movie.id),
            aggregate_version=movie.version, payload={"movie_id": movie.id, "version": movie.version}))

    async def delete(self, movie_id: int) -> None:
        movie = await self.repo.locked(movie_id)
        if movie is None:
            raise ApplicationError("movie_not_found", "Movie not found", 404)
        movie.is_active = False
        movie.version += 1
        self.event(movie, "movie.deleted")
        await self.session.commit()
