"""Data adapters, separate from prediction. MovieLens timestamps are Unix seconds."""
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import EngineConfig
from .data import Rating, Snapshot


def load_movielens_100k(path: str | Path) -> list[Rating]:
    rows = []
    with Path(path).open(encoding="ascii") as source:
        for line in source:
            user, movie, value, timestamp = line.split()
            rows.append(Rating(int(user), int(movie), float(value), int(timestamp)))
    # Validate bounds and uniqueness without modifying the observations.
    Snapshot(rows, config=EngineConfig(min_rating=1.0))
    return rows


async def load_database(session: AsyncSession, config: EngineConfig | None = None) -> Snapshot:
    """Caller must use one REPEATABLE READ transaction for a consistent snapshot."""
    from app.models import Movie, MovieView
    from app.models import Rating as StoredRating

    movies = list((await session.scalars(select(Movie.id).where(Movie.is_active))).all())
    rows = (await session.execute(select(StoredRating.user_id, StoredRating.movie_id, StoredRating.value)
            .join(Movie, Movie.id == StoredRating.movie_id).where(Movie.is_active))).all()
    views = (await session.execute(select(MovieView.movie_id, func.count())
             .join(Movie, Movie.id == MovieView.movie_id).where(Movie.is_active)
             .group_by(MovieView.movie_id))).all()
    return Snapshot((Rating(u, m, float(v)) for u, m, v in rows), movies,
                    {movie: count for movie, count in views}, config)
