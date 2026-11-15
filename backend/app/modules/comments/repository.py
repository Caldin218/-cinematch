from uuid import UUID

from sqlalchemy import delete, false, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import Pagination
from app.models import CommentLike, Movie, MovieComment, User


class CommentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def active_movie(self, movie_id: int):
        return await self.session.scalar(select(Movie.id).where(Movie.id == movie_id, Movie.is_active).with_for_update(read=True))

    async def active_comment(self, comment_id: int):
        return await self.session.scalar(select(MovieComment.id).join(Movie, Movie.id == MovieComment.movie_id)
            .where(MovieComment.id == comment_id, Movie.is_active).with_for_update(read=True))

    async def listing(self, movie_id: int, paging: Pagination, user_id: UUID | None):
        likes = select(func.count()).where(CommentLike.comment_id == MovieComment.id).correlate(MovieComment).scalar_subquery()
        liked = select(CommentLike.comment_id).where(CommentLike.comment_id == MovieComment.id,
            CommentLike.user_id == user_id).correlate(MovieComment).exists() if user_id else false()
        rows = (await self.session.execute(select(MovieComment, User.display_name, likes, liked).join(User, User.id == MovieComment.user_id)
            .where(MovieComment.movie_id == movie_id).order_by(MovieComment.created_at.desc(), MovieComment.id.desc())
            .offset(paging.offset).limit(paging.page_size))).all()
        total = await self.session.scalar(select(func.count()).select_from(MovieComment).where(MovieComment.movie_id == movie_id))
        return rows, total or 0

    async def add(self, movie_id: int, user_id: UUID, body: str):
        comment = MovieComment(movie_id=movie_id, user_id=user_id, body=body)
        self.session.add(comment)
        await self.session.flush()
        return comment

    async def like(self, comment_id: int, user_id: UUID, enabled: bool):
        if enabled:
            await self.session.execute(insert(CommentLike).values(comment_id=comment_id, user_id=user_id).on_conflict_do_nothing())
        else:
            await self.session.execute(delete(CommentLike).where(CommentLike.comment_id == comment_id, CommentLike.user_id == user_id))
