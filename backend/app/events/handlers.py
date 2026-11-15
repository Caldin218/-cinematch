"""Scheduling commits atomically with the consumer receipt; Redis is advisory."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.events.schema import PAYLOADS, EventEnvelope
from app.models import User
from app.modules.recommendations.scheduling import schedule_statement


def invalidate_user_recommendations(session: Session, event: EventEnvelope) -> None:
    # Older outbox events can refer to a user that no longer exists.
    if session.get(User, event.user_id) is not None:
        session.execute(schedule_statement(event.user_id, get_settings().recommendation_batch_seconds))


def invalidate_catalog_recommendations(session: Session, event: EventEnvelope) -> None:
    # Catalog changes affect every user's candidate set, including cold starts.
    for user_id in session.scalars(select(User.id).where(User.status == "active")):
        session.execute(schedule_statement(user_id, get_settings().recommendation_batch_seconds))


HANDLERS = {name: (invalidate_catalog_recommendations if name in
    {"movie.created", "movie.updated", "movie.deleted"} else invalidate_user_recommendations)
    for name in PAYLOADS}
