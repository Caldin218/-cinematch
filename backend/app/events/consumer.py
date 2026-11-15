import logging

from redis.exceptions import ResponseError
from sqlalchemy.dialects.postgresql import insert

from app.events.handlers import HANDLERS
from app.events.publisher import STREAM
from app.events.schema import EventEnvelope, envelope
from app.models import OutboxEvent, ProcessedEvent

logger = logging.getLogger(__name__)


class EventConsumer:
    def __init__(self, sessions, redis, name, group="recommendations-v1", stream=STREAM,
                 handlers=None, claim_idle_ms=60000):
        self.sessions, self.redis = sessions, redis
        self.name, self.group, self.stream = name, group, stream
        self.handlers = HANDLERS if handlers is None else handlers
        self.claim_idle_ms = claim_idle_ms
        self.claim_cursor = "0-0"

    def ensure_group(self):
        try:
            self.redis.xgroup_create(self.stream, self.group, id="0-0", mkstream=True)
        except ResponseError as error:
            if not str(error).startswith("BUSYGROUP"):
                raise

    def process(self, message_id, fields):
        event = EventEnvelope.model_validate_json(fields["event"])
        handler = self.handlers[event.event_type]  # Unsupported routing never ACKs.
        with self.sessions.begin() as session:
            source = session.get(OutboxEvent, event.event_id)
            if source is None or envelope(source) != event:
                raise ValueError("Event does not match PostgreSQL source")
            receipt = session.scalar(insert(ProcessedEvent).values(
                consumer_group=self.group, event_id=event.event_id
            ).on_conflict_do_nothing().returning(ProcessedEvent.event_id))
            if receipt is not None:
                handler(session, event)
        # Including duplicate delivery: only ACK after a committed receipt exists.
        self.redis.xack(self.stream, self.group, message_id)

    def _process_batch(self, messages, stopping):
        for message_id, fields in messages:
            if stopping():
                break
            try:
                self.process(message_id, fields)
            except Exception as error:
                # Remain pending for recovery; never log payloads or credentials.
                logger.error("event_failed group=%s entry=%s error=%s",
                    self.group, message_id, type(error).__name__)

    def poll(self, stopping=lambda: False):
        self.ensure_group()
        claimed = self.redis.xautoclaim(self.stream, self.group, self.name,
            min_idle_time=self.claim_idle_ms, start_id=self.claim_cursor, count=20)
        self.claim_cursor = claimed[0]
        self._process_batch(claimed[1], stopping)
        if len(claimed) > 2 and claimed[2]:
            logger.error("pending_entries_missing group=%s count=%s", self.group, len(claimed[2]))
        if not stopping():
            batches = self.redis.xreadgroup(self.group, self.name, {self.stream: ">"}, count=20, block=1000)
            for _, messages in batches:
                self._process_batch(messages, stopping)
