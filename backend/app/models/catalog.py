from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import TimestampMixin


class Movie(TimestampMixin, Base):
    __tablename__ = "movies"
    __table_args__ = (
        CheckConstraint("length(btrim(title)) BETWEEN 1 AND 255", name="title_length"),
        CheckConstraint("release_year BETWEEN 1888 AND 9999", name="release_year_range"),
        CheckConstraint("runtime_minutes > 0", name="runtime_positive"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint("updated_at >= created_at", name="timestamp_order"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_title: Mapped[str | None] = mapped_column(String(255))
    trailer_youtube_id: Mapped[str | None] = mapped_column(String(11))
    synopsis: Mapped[str | None] = mapped_column(Text)
    release_year: Mapped[int | None] = mapped_column(SmallInteger)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    poster_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


Index("ix_movies_active_year", Movie.release_year.desc().nullslast(), Movie.id, postgresql_where=text("is_active"))
Index("ix_movies_active_title_prefix", func.lower(Movie.title).label("title_lower"), Movie.id,
      postgresql_ops={"title_lower": "text_pattern_ops"}, postgresql_where=text("is_active"))


class Genre(TimestampMixin, Base):
    __tablename__ = "genres"
    __table_args__ = (
        CheckConstraint("name = btrim(name) AND length(name) BETWEEN 1 AND 80", name="name_nonempty"),
        CheckConstraint("updated_at >= created_at", name="timestamp_order"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)


Index("uq_genres_name_lower", func.lower(Genre.name), unique=True)


class MovieGenre(Base):
    __tablename__ = "movie_genres"
    movie_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True)
    genre_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("genres.id", ondelete="RESTRICT"), primary_key=True)


Index("ix_movie_genres_genre_movie", MovieGenre.genre_id, MovieGenre.movie_id)
