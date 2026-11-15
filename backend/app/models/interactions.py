from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Index, Numeric, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import CreatedAtMixin, TimestampMixin


class Rating(TimestampMixin, Base):
    __tablename__ = "ratings"
    __table_args__ = (
        CheckConstraint("value BETWEEN 0.5 AND 5", name="value_range"),
        CheckConstraint("updated_at >= created_at", name="timestamp_order"),
    )
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    movie_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("movies.id", ondelete="RESTRICT"), primary_key=True)
    value: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)


Index("ix_ratings_movie_user", Rating.movie_id, Rating.user_id)
Index("ix_ratings_user_updated", Rating.user_id, Rating.updated_at.desc(), Rating.movie_id)


class MovieView(Base):
    __tablename__ = "movie_views"
    __table_args__ = (UniqueConstraint("user_id", "request_id", name="uq_movie_views_user_request"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    movie_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("movies.id", ondelete="RESTRICT"), nullable=False)
    request_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


Index("ix_movie_views_user_time", MovieView.user_id, MovieView.viewed_at.desc(), MovieView.id)
Index("ix_movie_views_movie_time", MovieView.movie_id, MovieView.viewed_at.desc())
Index("ix_movie_views_time", MovieView.viewed_at)


class UserFavorite(CreatedAtMixin, Base):
    __tablename__ = "user_favorites"
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    movie_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True)


Index("ix_user_favorites_user_created", UserFavorite.user_id, UserFavorite.created_at.desc(), UserFavorite.movie_id)
Index("ix_user_favorites_movie", UserFavorite.movie_id)


class Watchlist(CreatedAtMixin, Base):
    __tablename__ = "watchlists"
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    movie_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True)


Index("ix_watchlists_user_created", Watchlist.user_id, Watchlist.created_at.desc(), Watchlist.movie_id)
Index("ix_watchlists_movie", Watchlist.movie_id)
