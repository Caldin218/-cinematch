"""Handlers mutate PostgreSQL only, within the consumer's receipt transaction."""
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.events.schema import PAYLOADS, EventEnvelope
from app.models import Recommendation


def invalidate_user_recommendations(session: Session, event: EventEnvelope) -> None:
    session.execute(delete(Recommendation).where(Recommendation.user_id == event.user_id))


def invalidate_catalog_recommendations(session: Session, event: EventEnvelope) -> None:
    session.execute(delete(Recommendation).where(Recommendation.movie_id == event.payload["movie_id"]))


HANDLERS = {name: (invalidate_catalog_recommendations if name in
    {"movie.created", "movie.updated", "movie.deleted"} else invalidate_user_recommendations)
    for name in PAYLOADS}
