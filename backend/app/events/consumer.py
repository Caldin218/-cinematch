import json
import logging
import threading
import time
from contextlib import contextmanager

from redis.exceptions import RedisError, ResponseError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import InterfaceError, OperationalError

from app.events.handlers import HANDLERS
from app.events.publisher import STREAM
from app.events.reliability import ACK, DEAD, HEARTBEAT, RETRY, RetryPolicy
from app.events.schema import EventEnvelope, envelope
from app.models import OutboxEvent, ProcessedEvent

logger = logging.getLogger(__name__)


class InvalidEvent(ValueError):
    pass


class EventConsumer:
    def __init__(self, sessions, redis, name, group="recommendations-v1", stream=STREAM,
                 handlers=None, claim_idle_ms=60000, retry_policy=None):
        self.sessions, self.redis = sessions, redis
        self.name, self.group, self.stream = name, group, stream
        self.handlers = HANDLERS if handlers is None else handlers
        self.claim_idle_ms = claim_idle_ms
        self.retry_policy = retry_policy or RetryPolicy()
        self.claim_cursor = "0-0"
        self.metrics = dict(processed_total=0, failed_total=0, retried_total=0,
                            pending_messages=0, processing_duration=0.0, consumer_lag=0)
        self.healthy = False
        self.last_error = None

    def ensure_group(self):
        try:
            self.redis.xgroup_create(self.stream, self.group, id="0-0", mkstream=True)
        except ResponseError as error:
            if not str(error).startswith("BUSYGROUP"):
                raise

    def state_key(self, message_id):
        return f"{self.stream}:retry:{self.group}:{message_id}"

    @contextmanager
    def heartbeat(self, message_id):
        done = threading.Event()
        def refresh():
            while not done.wait(max(0.01, self.claim_idle_ms / 3000)):
                try:
                    if not self.redis.eval(HEARTBEAT, 1, self.stream, self.group, message_id, self.name):
                        return
                except RedisError:
                    return  # Receipt uniqueness still protects PostgreSQL effects.
        thread = threading.Thread(target=refresh, daemon=True)
        thread.start()
        try:
            yield
        finally:
            done.set()
            thread.join(timeout=4)

    def process(self, message_id, fields):
        try:
            incoming = EventEnvelope.model_validate_json(fields["event"])
            handler = self.handlers[incoming.event_type]
        except (ValueError, KeyError, TypeError) as error:
            raise InvalidEvent("Invalid envelope or unsupported route") from error
        with self.sessions.begin() as session:
            source = session.get(OutboxEvent, incoming.event_id)
            if source is None or envelope(source) != incoming:
                raise InvalidEvent("Event does not match PostgreSQL source")
            receipt = session.scalar(insert(ProcessedEvent).values(
                consumer_group=self.group, event_id=incoming.event_id
            ).on_conflict_do_nothing().returning(ProcessedEvent.event_id))
            if receipt is not None:
                handler(session, incoming)
        # Preserve this explicit ACK after commit; repeat delivery is harmless.
        self.redis.eval(ACK, 2, self.stream, self.state_key(message_id),
                        self.group, message_id, self.name)

    def _process_batch(self, messages, stopping):
        for message_id, fields in messages:
            if stopping():
                break
            started = time.monotonic()
            key = self.state_key(message_id)
            try:
                state = self.redis.hgetall(key)
                if float(state.get("due", 0)) > time.time():
                    continue
                failures = int(state.get("failures", 0))
                infrastructure_failures = int(state.get("infrastructure_failures", 0))
                if failures or infrastructure_failures:
                    self.metrics["retried_total"] += 1
                with self.heartbeat(message_id):
                    try:
                        self.process(message_id, fields)
                        self.metrics["processed_total"] += 1
                        self.last_error = None
                    except Exception as error:
                        self.metrics["failed_total"] += 1
                        self.last_error = type(error).__name__
                        self.healthy = False
                        logger.error("event_failed group=%s entry=%s error=%s",
                                     self.group, message_id, type(error).__name__)
                        # Infrastructure failures remain pending, without consuming poison budget.
                        if isinstance(error, (RedisError, OperationalError, InterfaceError)):
                            self.redis.eval(RETRY, 2, self.stream, key, self.group, message_id,
                                            self.name, failures, time.time() + self.retry_policy.delay(infrastructure_failures + 1),
                                            infrastructure_failures + 1)
                        elif isinstance(error, InvalidEvent) or failures >= self.retry_policy.max_retries:
                            self.redis.eval(DEAD, 3, self.stream, key, self.stream + ":dead",
                                            self.group, message_id, self.name, type(error).__name__,
                                            failures + 1, json.dumps(fields))
                        else:
                            self.redis.eval(RETRY, 2, self.stream, key, self.group, message_id,
                                            self.name, failures + 1,
                                            time.time() + self.retry_policy.delay(failures + 1), 0)
            finally:
                self.metrics["processing_duration"] += time.monotonic() - started

    def poll(self, stopping=lambda: False):
        try:
            self.ensure_group()
            claimed = self.redis.xautoclaim(self.stream, self.group, self.name,
                min_idle_time=self.claim_idle_ms, start_id=self.claim_cursor, count=1)
            self.claim_cursor = claimed[0]
            self._process_batch(claimed[1], stopping)
            if len(claimed) > 2 and claimed[2]:
                raise RuntimeError("Pending entries deleted externally; replay outbox required")
            if not stopping():
                batches = self.redis.xreadgroup(self.group, self.name, {self.stream: ">"}, count=1, block=1000)
                for _, messages in batches:
                    self._process_batch(messages, stopping)
            self.metrics["pending_messages"] = self.redis.xpending(self.stream, self.group)["pending"]
            groups = self.redis.xinfo_groups(self.stream)
            self.metrics["consumer_lag"] = next(g.get("lag") for g in groups if g["name"] == self.group)
            self.healthy = self.last_error is None
        except Exception as error:
            self.healthy = False
            self.last_error = type(error).__name__
            raise

    def status(self):
        return {"healthy": self.healthy, "last_error": self.last_error, **self.metrics}
