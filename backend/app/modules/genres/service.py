import logging
from pydantic import TypeAdapter, ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.errors import ApplicationError
from app.models import Genre
from app.modules.genres.repository import GenreRepository
from app.modules.genres.schemas import GenreInput, GenreRead

logger = logging.getLogger(__name__)

class GenreService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self.session, self.redis = session, redis
        self.repo = GenreRepository(session)
        # Separate databases in integration tests and separate configured deployments.
        self.key = "cinematch:genres:v1:" + session.bind.url.database

    async def listing(self) -> list[GenreRead]:
        adapter = TypeAdapter(list[GenreRead])
        try:
            cached = await self.redis.get(self.key)
            if cached is not None:
                return adapter.validate_json(cached)
        except (RedisError, ValidationError):
            logger.warning("genre_cache_read_failed")
        result = [GenreRead.model_validate(genre) for genre in await self.repo.listing()]
        try:
            await self.redis.set(self.key, adapter.dump_json(result), ex=60)
        except RedisError:
            logger.warning("genre_cache_write_failed")
        return result

    async def invalidate(self) -> None:
        try:
            await self.redis.delete(self.key)
        except RedisError:
            logger.warning("genre_cache_invalidation_failed")

    async def change(self, data: GenreInput | None, genre_id: int | None = None) -> GenreRead | None:
        genre = await self.repo.locked(genre_id) if genre_id is not None else Genre()
        if genre is None:
            raise ApplicationError("genre_not_found", "Genre not found", 404)
        if data is None:
            await self.session.delete(genre)
        else:
            genre.name = data.name
            self.session.add(genre)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            code = getattr(exc.orig, "sqlstate", None)
            if code in ("23505", "23503"):
                raise ApplicationError("genre_conflict", "Genre already exists or is assigned to movies", 409) from exc
            raise
        await self.invalidate()
        return GenreRead.model_validate(genre) if data is not None else None
