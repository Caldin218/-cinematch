from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import Page, Pagination
from app.core.errors import ApplicationError
from app.models import User

from .repository import CommentRepository
from .schemas import CommentRead


class CommentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CommentRepository(session)

    async def require_movie(self, movie_id: int):
        if not await self.repo.active_movie(movie_id):
            raise ApplicationError("movie_not_found", "Movie not found", 404)

    async def listing(self, movie_id: int, paging: Pagination, user: User | None):
        await self.require_movie(movie_id)
        rows, total = await self.repo.listing(movie_id, paging, user.id if user else None)
        return Page(items=[CommentRead(id=c.id, movie_id=c.movie_id, username=name, body=c.body,
            created_at=c.created_at, likes=count, liked=bool(liked)) for c, name, count, liked in rows],
            total=total, page=paging.page, page_size=paging.page_size)

    async def add(self, movie_id: int, user: User, body: str):
        await self.require_movie(movie_id)
        c = await self.repo.add(movie_id, user.id, body)
        result = CommentRead(id=c.id, movie_id=movie_id, username=user.display_name,
            body=c.body, created_at=c.created_at, likes=0, liked=False)
        await self.session.commit()
        return result

    async def like(self, comment_id: int, user: User, enabled: bool):
        if not await self.repo.active_comment(comment_id):
            raise ApplicationError("comment_not_found", "Comment not found", 404)
        await self.repo.like(comment_id, user.id, enabled)
        await self.session.commit()
