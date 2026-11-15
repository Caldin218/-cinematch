from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MovieComment(Base):
    __tablename__ = "movie_comments"
    __table_args__ = (CheckConstraint("length(btrim(body)) BETWEEN 1 AND 2000", name="body_length"),)
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    movie_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

Index("ix_movie_comments_movie_time", MovieComment.movie_id, MovieComment.created_at.desc(), MovieComment.id.desc())

class CommentLike(Base):
    __tablename__ = "comment_likes"
    comment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("movie_comments.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
