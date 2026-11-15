"""PostgreSQL upsert: first interaction sets a bounded batching deadline.

Updates advance the revision without extending an already pending deadline.
Both async API sessions and synchronous event handlers use this statement.
"""
from uuid import UUID

from sqlalchemy import case, func
from sqlalchemy.dialects.postgresql import Insert, insert

from app.models import RecommendationJob


def schedule_statement(user_id: UUID, batch_seconds: float) -> Insert:
    from datetime import timedelta

    job = RecommendationJob
    due = func.clock_timestamp() + timedelta(seconds=batch_seconds)
    return insert(job).values(user_id=user_id, due_at=due).on_conflict_do_update(
        index_elements=[job.user_id], set_={
            "revision": job.revision + 1,
            "due_at": case((job.revision == job.completed_revision, due), else_=job.due_at),
        })
