import os
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from redis.exceptions import ConnectionError
from sqlalchemy import event, update
from sqlalchemy.orm import sessionmaker

from app.events.consumer import EventConsumer
from app.events.publisher import OutboxPublisher
from app.events.schema import EventEnvelope, envelope, new_event
from app.models import OutboxEvent, ProcessedEvent


def sample():
    user = uuid4()
    return new_event(event_type="movie.favorite_added", aggregate_type="user_interactions",
        aggregate_id=str(user), aggregate_version=1, user_id=user,
        payload={"user_id": str(user), "movie_id": 1})


@pytest.mark.parametrize("field,value", [("schema_version", True), ("schema_version", 1.0),
    ("schema_version", 2), ("event_type", "unknown"), ("aggregate_id", "wrong"),
    ("payload", {"movie_id": 0}), ("occurred_at", "2026-01-01T00:00:00")])
def test_invalid_envelope(field, value):
    data = envelope(sample()).model_dump()
    data[field] = value
    with pytest.raises(ValidationError):
        EventEnvelope.model_validate(data)


def test_envelope_round_trip():
    original = envelope(sample())
    assert EventEnvelope.model_validate_json(original.model_dump_json()) == original


@pytest.fixture
def infra():
    if os.getenv("RUN_INTEGRATION") != "1":
        pytest.skip("Requires PostgreSQL and Redis")
    from test_database_schema import alembic_config, temporary_database

    from alembic import command
    from app.core.config import get_settings
    from app.core.redis import create_redis_client
    with temporary_database() as engine:
        with engine.connect() as connection:
            command.upgrade(alembic_config(connection), "head")
        redis = create_redis_client(get_settings())
        stream = "test:events:" + uuid4().hex
        try:
            redis.ping()
            yield engine, sessionmaker(engine, expire_on_commit=False), redis, stream
        finally:
            redis.delete(stream)
            redis.close()


def seed(sessions):
    with sessions.begin() as session:
        row = sample()
        session.add(row)
    return row.id


def test_publish_restart_outage_replay_and_dedup(infra):
    engine, sessions, redis, stream = infra
    identifier = seed(sessions)
    unavailable = Mock()
    unavailable.xadd.side_effect = ConnectionError("offline")
    assert OutboxPublisher(sessions, unavailable, stream).publish_one()
    with sessions.begin() as session:
        row = session.get(OutboxEvent, identifier)
        assert row.published_at is None and row.publish_attempts == 1
        row.next_attempt_at = datetime.now(timezone.utc)
    publisher = OutboxPublisher(sessions, redis, stream)
    assert publisher.publish_one()
    assert not OutboxPublisher(sessions, redis, stream).publish_one()
    publisher.replay(identifier)
    effects = []
    consumer = EventConsumer(sessions, redis, "one", stream=stream,
        handlers={"movie.favorite_added": lambda session, event: effects.append(event.event_id)})
    consumer.poll()
    consumer.poll()
    assert effects == [identifier]
    assert redis.xpending(stream, consumer.group)["pending"] == 0
    # Lost stream recovery retains PostgreSQL as authority and receipts deduplicate replay.
    redis.delete(stream)
    publisher.replay(identifier)
    consumer.poll()
    consumer.poll()
    assert effects == [identifier]


def test_crash_after_xadd_before_commit(infra):
    engine, sessions, redis, stream = infra
    identifier = seed(sessions)
    def crash(session):
        raise RuntimeError("commit crash")
    event.listen(sessions, "before_commit", crash)
    try:
        with pytest.raises(RuntimeError):
            OutboxPublisher(sessions, redis, stream).publish_one()
    finally:
        event.remove(sessions, "before_commit", crash)
    assert redis.xlen(stream) == 1
    assert OutboxPublisher(sessions, redis, stream).publish_one()
    assert redis.xlen(stream) == 2
    with sessions() as session:
        assert session.get(OutboxEvent, identifier).published_at is not None


def test_rollback_and_pending_recovery(infra):
    engine, sessions, redis, stream = infra
    with pytest.raises(RuntimeError), sessions.begin() as session:
        session.add(sample())
        raise RuntimeError("rollback")
    assert not OutboxPublisher(sessions, redis, stream).publish_one()
    identifier = seed(sessions)
    OutboxPublisher(sessions, redis, stream).publish_one()
    first = EventConsumer(sessions, redis, "crashed", stream=stream)
    first.ensure_group()
    batches = redis.xreadgroup(first.group, first.name, {stream: ">"}, count=1)
    def broken(session, incoming):
        session.execute(update(OutboxEvent).where(OutboxEvent.id == identifier).values(last_error="effect"))
        raise RuntimeError("handler crash")
    first.handlers = {"movie.favorite_added": broken}
    with pytest.raises(RuntimeError):
        first.process(*batches[0][1][0])
    with sessions() as session:
        assert session.get(OutboxEvent, identifier).last_error is None
        assert session.get(ProcessedEvent, (first.group, identifier)) is None
    second = EventConsumer(sessions, redis, "replacement", stream=stream, claim_idle_ms=0)
    second.poll()
    assert redis.xpending(stream, first.group)["pending"] == 0
    with sessions() as session:
        assert session.get(ProcessedEvent, (first.group, identifier)) is not None


def test_multiple_consumers_and_ack_failure(infra):
    from concurrent.futures import ThreadPoolExecutor
    _, sessions, redis, stream = infra
    identifiers = [seed(sessions) for _ in range(6)]
    publisher = OutboxPublisher(sessions, redis, stream)
    while publisher.publish_one():
        pass
    workers = [EventConsumer(sessions, redis, str(i), stream=stream) for i in range(2)]
    workers[0].ensure_group()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda worker: [worker.poll() for _ in range(4)], workers))
    with sessions() as session:
        assert all(session.get(ProcessedEvent, (workers[0].group, identifier)) for identifier in identifiers)
    assert redis.xpending(stream, workers[0].group)["pending"] == 0
    publisher.replay(identifiers[0])
    message = redis.xreadgroup(workers[0].group, "ack-fail", {stream: ">"})[0][1][0]
    failing = Mock(wraps=redis)
    failing.eval.side_effect = ConnectionError("ACK lost")
    worker = EventConsumer(sessions, failing, "ack-fail", stream=stream)
    with pytest.raises(ConnectionError):
        worker.process(*message)
    workers[1].claim_idle_ms = 0
    workers[1].poll()
    assert redis.xpending(stream, worker.group)["pending"] == 0


def test_shutdown_does_not_admit_batch():
    worker = EventConsumer(Mock(), Mock(), "stopping")
    worker.process = Mock()
    worker._process_batch([("1-0", {})], lambda: True)
    worker.process.assert_not_called()


def test_worker_signal_finishes_and_closes(monkeypatch):
    import signal

    from app.events import worker
    callbacks = {}
    engine, redis = Mock(), Mock()
    monkeypatch.setattr(worker.signal, "signal", lambda sig, callback: callbacks.setdefault(sig, callback))
    monkeypatch.setattr(worker, "create_database_engine", lambda settings: engine)
    monkeypatch.setattr(worker, "create_redis_client", lambda settings: redis)
    monkeypatch.setattr(worker, "get_session_factory", lambda engine: Mock())
    monkeypatch.setattr("sqlalchemy.event.listens_for", lambda *args: lambda function: function)
    publisher = Mock()
    def publish():
        callbacks[signal.SIGTERM](signal.SIGTERM, None)
        return True
    publisher.publish_one.side_effect = publish
    monkeypatch.setattr(worker, "OutboxPublisher", lambda *args: publisher)
    monkeypatch.setattr("sys.argv", ["worker", "publisher"])
    worker.main()
    publisher.publish_one.assert_called_once()
    redis.close.assert_called_once()
    engine.dispose.assert_called_once()


def test_ambiguous_xadd_timeout_retries_same_identity(infra):
    _, sessions, redis, stream = infra
    identifier = seed(sessions)
    ambiguous = Mock(wraps=redis)
    def delivered_then_timeout(*args, **kwargs):
        redis.xadd(*args, **kwargs)
        raise ConnectionError("confirmation lost")
    ambiguous.xadd.side_effect = delivered_then_timeout
    OutboxPublisher(sessions, ambiguous, stream).publish_one()
    with sessions.begin() as session:
        row = session.get(OutboxEvent, identifier)
        assert row.published_at is None
        row.next_attempt_at = datetime.now(timezone.utc)
    OutboxPublisher(sessions, redis, stream).publish_one()
    messages = redis.xrange(stream)
    assert len(messages) == 2
    assert all(EventEnvelope.model_validate_json(fields["event"]).event_id == identifier for _, fields in messages)


def test_invalid_event_goes_to_dead_stream(infra):
    import json
    _, sessions, redis, stream = infra
    redis.xadd(stream, {"event": "not-json"})
    worker = EventConsumer(sessions, redis, "invalid", stream=stream)
    worker.poll()
    dead = redis.xrange(stream + ":dead")
    assert len(dead) == 1
    assert json.loads(dead[0][1]["fields"]) == {"event": "not-json"}
    assert redis.xpending(stream, worker.group)["pending"] == 0
    redis.delete(stream + ":dead")


def test_retry_backoff_restart_and_exhaustion(infra):
    from app.events.reliability import RetryPolicy
    _, sessions, redis, stream = infra
    identifier = seed(sessions)
    OutboxPublisher(sessions, redis, stream).publish_one()
    calls = []
    def broken(session, incoming):
        calls.append(1)
        session.execute(update(OutboxEvent).where(OutboxEvent.id == identifier).values(last_error="rollback"))
        raise RuntimeError("poison")
    def worker(name):
        return EventConsumer(sessions, redis, name, stream=stream, claim_idle_ms=0,
            handlers={"movie.favorite_added": broken}, retry_policy=RetryPolicy(2, 10, 40))
    first = worker("first")
    first.poll()
    entry = redis.xrange(stream)[0][0]
    key = first.state_key(entry)
    assert redis.hget(key, "failures") == "1"
    worker("early").poll()
    assert len(calls) == 1
    for name in ["restart", "exhaust"]:
        redis.hset(key, "due", 0)
        worker(name).poll()
    assert len(calls) == 3
    assert len(redis.xrange(stream + ":dead")) == 1
    assert redis.xpending(stream, first.group)["pending"] == 0
    with sessions() as session:
        assert session.get(ProcessedEvent, (first.group, identifier)) is None
        assert session.get(OutboxEvent, identifier).last_error is None
    redis.delete(stream + ":dead")


def test_database_outage_preserves_retry_budget(infra):
    from sqlalchemy.exc import OperationalError
    _, sessions, redis, stream = infra
    seed(sessions)
    OutboxPublisher(sessions, redis, stream).publish_one()
    offline = Mock()
    offline.begin.side_effect = OperationalError("connect", {}, Exception("offline"))
    worker = EventConsumer(offline, redis, "offline", stream=stream)
    worker.poll()
    entry = redis.xrange(stream)[0][0]
    assert redis.hget(worker.state_key(entry), "failures") == "0"
    assert redis.xpending(stream, worker.group)["pending"] == 1
    assert not worker.status()["healthy"]
    redis.hset(worker.state_key(entry), "due", 0)
    EventConsumer(sessions, redis, "recovered", stream=stream, claim_idle_ms=0).poll()
    assert redis.xpending(stream, worker.group)["pending"] == 0


def test_dead_letter_outage_does_not_ack(infra):
    _, sessions, redis, stream = infra
    redis.xadd(stream, {"event": "invalid"})
    failing = Mock(wraps=redis)
    failing.eval.side_effect = ConnectionError("Redis unavailable")
    worker = EventConsumer(sessions, failing, "offline", stream=stream)
    with pytest.raises(ConnectionError):
        worker.poll()
    assert redis.xpending(stream, worker.group)["pending"] == 1
    EventConsumer(sessions, redis, "restore", stream=stream, claim_idle_ms=0).poll()
    assert redis.xpending(stream, worker.group)["pending"] == 0
    redis.delete(stream + ":dead")


def test_long_running_handler_heartbeat(infra):
    import time
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    _, sessions, redis, stream = infra
    seed(sessions)
    OutboxPublisher(sessions, redis, stream).publish_one()
    entered, release = Event(), Event()
    def slow(session, incoming):
        entered.set()
        assert release.wait(5)
    worker = EventConsumer(sessions, redis, "slow", stream=stream, claim_idle_ms=150,
        handlers={"movie.favorite_added": slow})
    with ThreadPoolExecutor() as pool:
        future = pool.submit(worker.poll)
        try:
            assert entered.wait(5)
            time.sleep(0.4)
            claimed = redis.xautoclaim(stream, worker.group, "competitor", 150, "0-0")
            assert claimed[1] == []
        finally:
            release.set()
        future.result()
    assert redis.xpending(stream, worker.group)["pending"] == 0


def test_exponential_retry_policy():
    from app.events.reliability import RetryPolicy
    policy = RetryPolicy(5, 2, 10)
    assert [policy.delay(i) for i in range(1, 6)] == [2, 4, 8, 10, 10]


def test_consumer_commit_failure_never_acknowledges(infra):
    _, sessions, redis, stream = infra
    identifier = seed(sessions)
    OutboxPublisher(sessions, redis, stream).publish_one()
    worker = EventConsumer(sessions, redis, "commit-fail", stream=stream)
    def crash(session):
        raise RuntimeError("commit failure")
    event.listen(sessions, "before_commit", crash)
    try:
        worker.poll()
    finally:
        event.remove(sessions, "before_commit", crash)
    assert redis.xpending(stream, worker.group)["pending"] == 1
    with sessions() as session:
        assert session.get(ProcessedEvent, (worker.group, identifier)) is None
    entry = redis.xrange(stream)[0][0]
    redis.hset(worker.state_key(entry), "due", 0)
    EventConsumer(sessions, redis, "restart", stream=stream, claim_idle_ms=0).poll()
    assert redis.xpending(stream, worker.group)["pending"] == 0


def test_health_and_metrics_endpoint():
    import json
    from urllib.request import urlopen

    from app.events.health import serve_status
    worker = EventConsumer(Mock(), Mock(), "health")
    worker.healthy = True
    server = serve_status(worker, 0)
    try:
        address = f"http://127.0.0.1:{server.server_port}"
        with urlopen(address + "/health") as response:
            assert json.load(response)["healthy"] is True
        with urlopen(address + "/metrics") as response:
            metrics = response.read().decode()
            assert "processed_total 0" in metrics
            assert "processing_duration 0.0" in metrics
    finally:
        server.shutdown()
        server.server_close()
