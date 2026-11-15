from collections.abc import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Genre

class GenreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def listing(self) -> Sequence[Genre]:
        return (await self.session.scalars(select(Genre).order_by(Genre.name, Genre.id))).all()

    async def locked(self, genre_id: int) -> Genre | None:
        return await self.session.scalar(select(Genre).where(Genre.id == genre_id).with_for_update())
