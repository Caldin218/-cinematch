"""Explicit model registry for Alembic and database consumers."""

from app.models.auth import RefreshToken
from app.models.catalog import Genre, Movie, MovieGenre
from app.models.events import OutboxEvent, ProcessedEvent
from app.models.interactions import MovieView, Rating, UserFavorite, Watchlist
from app.models.recommendations import Recommendation, RecommendationJob
from app.models.users import User

__all__ = [
    "MovieComment", "CommentLike", "User", "Movie", "Genre", "MovieGenre", "Rating", "MovieView",
    "UserFavorite", "Watchlist", "OutboxEvent", "ProcessedEvent",
    "Recommendation", "RecommendationJob", "RefreshToken",
]

from app.models.comments import CommentLike, MovieComment
