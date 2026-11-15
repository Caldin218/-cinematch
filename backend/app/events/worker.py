"""Run with python -m app.events.worker publisher|consumer."""
import argparse
import logging
import signal
import socket
import threading
from uuid import UUID, uuid4

from app.core.config import get_settings
from app.core.database import create_database_engine, get_session_factory
from app.core.redis import create_redis_client
from app.events.consumer import EventConsumer
from app.events.publisher import STREAM, OutboxPublisher


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=["publisher", "consumer", "replay"])
    parser.add_argument("--stream", default=STREAM)
    parser.add_argument("--group", default="recommendations-v1")
    parser.add_argument("--name", default=f"{socket.gethostname()}-{uuid4().hex}")
    parser.add_argument("--event-id", type=UUID)
    args = parser.parse_args()
    if args.role == "replay" and args.event_id is None:
        parser.error("replay requires --event-id")
    if not args.group.strip() or len(args.group) > 100:
        parser.error("group must contain 1–100 nonblank characters")
    logging.basicConfig(level=logging.INFO)
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    settings = get_settings()
    engine = create_database_engine(settings)
    redis = create_redis_client(settings)
    # Bound database waits so shutdown is not held indefinitely by another transaction.
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def set_timeouts(connection, _):
        with connection.cursor() as cursor:
            cursor.execute("SET statement_timeout = '10s'")
            cursor.execute("SET lock_timeout = '5s'")
        connection.commit()
    sessions = get_session_factory(engine)
    worker = (OutboxPublisher(sessions, redis, args.stream) if args.role in {"publisher", "replay"}
              else EventConsumer(sessions, redis, args.name, args.group, args.stream))
    try:
        if args.role == "replay":
            OutboxPublisher(sessions, redis, args.stream).replay(args.event_id)
            return
        while not stop.is_set():
            try:
                if args.role == "publisher":
                    if not worker.publish_one():
                        stop.wait(0.5)
                else:
                    worker.poll(stop.is_set)
            except Exception as error:
                logging.error("worker_retry role=%s error=%s", args.role, type(error).__name__)
                stop.wait(2)
    finally:
        redis.close()
        engine.dispose()
        logging.info("worker_stopped role=%s", args.role)


if __name__ == "__main__":
    main()
