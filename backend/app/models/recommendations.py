from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        UniqueConstraint("user_id", "rank", name="uq_recommendations_user_rank"),
        CheckConstraint("rank > 0", name="rank_positive"),
        CheckConstraint("length(btrim(algorithm_version)) > 0", name="algorithm_nonempty"),
        CheckConstraint("generated_at >= source_cutoff", name="generation_order"),
        CheckConstraint(
            "(method = 'user_cf' AND predicted_rating BETWEEN 0.5 AND 5 AND predicted_rating IS NOT NULL AND popularity_score IS NULL) OR "
            "(method = 'popularity' AND popularity_score BETWEEN 0.5 AND 5 AND popularity_score IS NOT NULL AND predicted_rating IS NULL) OR "
            "(method = 'hybrid' AND predicted_rating BETWEEN 0.5 AND 5 AND predicted_rating IS NOT NULL AND popularity_score BETWEEN 0.5 AND 5 AND popularity_score IS NOT NULL) OR "
            "(method = 'catalog_fallback' AND predicted_rating IS NULL AND popularity_score IS NULL)",
            name="method_score_consistent",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    movie_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("movies.id", ondelete="RESTRICT"), primary_key=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[str] = mapped_column(String(24), nullable=False)
    predicted_rating: Mapped[Decimal | None] = mapped_column(Numeric(6, 5))
    popularity_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 5))
    ranking_score: Mapped[float | None] = mapped_column(Float)
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


Index("ix_recommendations_movie", Recommendation.movie_id)


class RecommendationJob(Base):
    """Durable coalescing queue and metadata, including successful empty results."""
    __tablename__ = "recommendation_jobs"

    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="1")
    completed_revision: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error: Mapped[str | None] = mapped_column(String(100))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_cutoff: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    algorithm_version: Mapped[str | None] = mapped_column(String(64))
    generation_seconds: Mapped[float | None] = mapped_column(Float)


Index("ix_recommendation_jobs_due", RecommendationJob.due_at)
