"""One short database transaction per XADD; crashes release row locks."""
from datetime import datetime, timedelta, timezone
from uuid import UUID

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.events.schema import envelope
from app.models import OutboxEvent

STREAM = "cinematch:events:v1"


class OutboxPublisher:
    def __init__(self, sessions: sessionmaker[Session], redis: Redis, stream: str = STREAM) -> None:
        self.sessions, self.redis, self.stream = sessions, redis, stream

    def publish_one(self) -> bool:
        with self.sessions.begin() as session:
            row = session.scalar(select(OutboxEvent).where(
                OutboxEvent.published_at.is_(None), OutboxEvent.next_attempt_at <= func.now()
            ).order_by(OutboxEvent.next_attempt_at, OutboxEvent.occurred_at, OutboxEvent.id)
                .with_for_update(skip_locked=True).limit(1))
            if row is None:
                return False
            row.publish_attempts += 1
            try:
                message = envelope(row).model_dump_json()
                # No MAXLEN: unacknowledged entries must not be silently evicted.
                confirmed_id = self.redis.xadd(self.stream, {"event": message})
                if not confirmed_id:
                    raise RedisError("XADD did not return an entry ID")
            except (RedisError, ValueError) as error:
                row.last_error = type(error).__name__
                row.next_attempt_at = datetime.now(timezone.utc) + timedelta(
                    seconds=min(300, 2 ** min(row.publish_attempts, 8)))
                return True
            # A failure/crash committing this update causes duplicate publication on retry.
            row.published_at = func.clock_timestamp()
            row.last_error = None
            return True


    def replay(self, event_id: UUID):
        """Explicit operator recovery; preserve event identity and publication history."""
        with self.sessions() as session:
            row = session.get(OutboxEvent, event_id)
            if row is None:
                raise ValueError("Unknown outbox event")
            confirmed = self.redis.xadd(self.stream, {"event": envelope(row).model_dump_json()})
            if not confirmed:
                raise RedisError("Replay XADD did not return an entry ID")
            return confirmed
