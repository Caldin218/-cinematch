"""Lease-based durable worker. No database locks are held during calculation."""
import logging
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models import Movie, MovieView, Rating, Recommendation, RecommendationJob
from app.modules.recommendations.cache import cache_key
from app.recommendation_engine.data import Rating as EngineRating
from app.recommendation_engine.data import Snapshot
from app.recommendation_engine.hybrid import Recommendation as EngineRecommendation
from app.recommendation_engine.hybrid import RecommendationEngine

ALGORITHM_VERSION = "hybrid-cf-popularity-v1"
logger = logging.getLogger(__name__)


class RecommendationWorker:
    def __init__(self, sessions: sessionmaker[Session], redis: Redis, settings: Settings):
        self.sessions, self.redis, self.settings = sessions, redis, settings
        self.metrics = dict(generated_total=0, failed_total=0, superseded_total=0,
                            generation_seconds=0.0)
        self.last_error: str | None = None

    def claim(self) -> tuple[UUID, int, UUID] | None:
        with self.sessions.begin() as session:
            job = session.scalar(select(RecommendationJob).where(
                RecommendationJob.revision > RecommendationJob.completed_revision,
                RecommendationJob.due_at <= func.clock_timestamp(),
                or_(RecommendationJob.lease_until.is_(None),
                    RecommendationJob.lease_until < func.clock_timestamp()),
            ).order_by(RecommendationJob.due_at).with_for_update(skip_locked=True).limit(1))
            if job is None:
                return None
            token = uuid4()
            job.lease_token = token
            now = datetime.now(timezone.utc)
            job.lease_until = now + timedelta(seconds=self.settings.recommendation_lease_seconds)
            # A superseded calculation must wait for the next batch window too.
            job.due_at = now + timedelta(seconds=self.settings.recommendation_batch_seconds)
            return job.user_id, job.revision, token

    def calculate(self, user_id: UUID) -> tuple[datetime, list[EngineRecommendation]]:
        # All source queries see the same committed database snapshot.
        with self.sessions() as session:
            session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
            cutoff = session.scalar(select(func.clock_timestamp()))
            assert cutoff is not None
            movies = list(session.scalars(select(Movie.id).where(Movie.is_active)))
            ratings = session.execute(select(Rating.user_id, Rating.movie_id, Rating.value)
                .join(Movie, Movie.id == Rating.movie_id).where(Movie.is_active)).all()
            views = session.execute(select(MovieView.movie_id, func.count())
                .join(Movie, Movie.id == MovieView.movie_id).where(Movie.is_active)
                .group_by(MovieView.movie_id)).all()
        snapshot = Snapshot((EngineRating(u, m, float(v)) for u, m, v in ratings),
                            movies, {movie: count for movie, count in views})
        return cutoff, RecommendationEngine(snapshot).recommend(user_id, self.settings.recommendation_top_n)

    def run_one(self) -> bool:
        try:
            claimed = self.claim()
        except Exception as error:
            self.last_error = type(error).__name__
            self.metrics["failed_total"] += 1
            raise
        if claimed is None:
            return False
        user_id, revision, token = claimed
        started = time.monotonic()
        try:
            cutoff, results = self.calculate(user_id)
            duration = time.monotonic() - started
            with self.sessions.begin() as session:
                job = session.get(RecommendationJob, user_id, with_for_update=True)
                if job is None or job.lease_token != token:
                    return True  # An expired lease was taken by another worker.
                job.lease_until = job.lease_token = None
                if job.revision != revision:
                    self.metrics["superseded_total"] += 1
                    return True  # A newer interaction arrived during calculation.
                generated = datetime.now(timezone.utc)
                session.execute(delete(Recommendation).where(Recommendation.user_id == user_id))
                for rank, result in enumerate(results, 1):
                    # The existing storage contract uses rating-scale popularity.
                    # Ranking itself remains the engine's hybrid ranking.
                    session.add(Recommendation(user_id=user_id, movie_id=result.movie_id, rank=rank,
                        method=result.method, ranking_score=result.score,
                        predicted_rating=result.predicted_rating,
                        popularity_score=0.5 + 4.5 * result.popularity_score,
                        algorithm_version=ALGORITHM_VERSION, source_cutoff=cutoff, generated_at=generated))
                job.completed_revision = revision
                job.generated_at, job.source_cutoff = generated, cutoff
                job.algorithm_version, job.generation_seconds = ALGORITHM_VERSION, duration
                job.attempts, job.last_error = 0, None
            # Failed cache deletion cannot undo committed results. Readers fence by revision.
            try:
                self.redis.delete(cache_key(user_id))
            except RedisError:
                logger.warning("recommendation_cache_invalidation_failed user=%s", user_id)
            self.metrics["generated_total"] += 1
            self.metrics["generation_seconds"] += duration
            self.last_error = None
            logger.info("recommendation_generated user=%s revision=%s seconds=%.6f algorithm=%s",
                        user_id, revision, duration, ALGORITHM_VERSION)
        except Exception as error:
            self.metrics["failed_total"] += 1
            self.last_error = type(error).__name__
            with self.sessions.begin() as session:
                job = session.get(RecommendationJob, user_id, with_for_update=True)
                if job is not None and job.lease_token == token:
                    job.lease_until = job.lease_token = None
                    job.attempts += 1
                    job.last_error = type(error).__name__
                    job.due_at = datetime.now(timezone.utc) + timedelta(
                        seconds=min(300, 2 ** min(job.attempts, 8)))
            logger.error("recommendation_failed user=%s error=%s", user_id, type(error).__name__)
        return True

    def status(self):
        return {"healthy": self.last_error is None, "last_error": self.last_error, **self.metrics}
