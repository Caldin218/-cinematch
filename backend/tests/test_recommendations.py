# ruff: noqa: F811
import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from redis.exceptions import ConnectionError
from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker
from test_auth import auth, client, database, login, register  # noqa: F401
from test_events import infra  # noqa: F401

from app.core.config import get_settings
from app.events.consumer import EventConsumer
from app.events.publisher import OutboxPublisher
from app.events.schema import new_event
from app.models import Movie, Rating, Recommendation, RecommendationJob, User
from app.modules.recommendations.cache import RecommendationCache, cache_key
from app.modules.recommendations.scheduling import schedule_statement
from app.modules.recommendations.schemas import RecommendationRead
from app.modules.recommendations.worker import RecommendationWorker


def ready():
    now = datetime.now(timezone.utc)
    return RecommendationRead(items=[], generated_at=now, source_cutoff=now,
        algorithm_version="test-v1", generation_seconds=0.1, status="ready")


def test_cache_hit_miss_ttl_and_invalidation():
    async def run():
        user = uuid4()
        redis = AsyncMock()
        redis.get.return_value = None
        cache = RecommendationCache(redis, 27)
        assert await cache.get(user, 1) is None
        await cache.put(user, 1, ready())
        args = redis.set.call_args
        assert args.args[0] == cache_key(user) and args.kwargs == {"ex": 27}
        redis.get.return_value = args.args[1]
        assert (await cache.get(user, 1)).status == "ready"
        assert await cache.get(user, 2) is None
        redis.delete.assert_awaited_with(cache_key(user))
    asyncio.run(run())


@pytest.mark.parametrize("damage", ["json", "user", "version", "nan", "shape"])
def test_cache_serialization_validation(damage):
    async def run():
        user = uuid4()
        redis = AsyncMock()
        cache = RecommendationCache(redis, 10)
        await cache.put(user, 1, ready())
        value = json.loads(redis.set.call_args.args[1])
        if damage == "user":
            value["user_id"] = str(uuid4())
        elif damage == "version":
            value["schema_version"] = 2
        elif damage == "nan":
            value["result"]["generation_seconds"] = float("nan")
        elif damage == "shape":
            value["result"]["items"] = [{"movie_id": 1, "rank": 2, "method": "catalog_fallback"}]
        redis.get.return_value = "invalid" if damage == "json" else json.dumps(value)
        assert await cache.get(user, 1) is None
        redis.delete.assert_awaited_once()
    asyncio.run(run())


def test_cache_outage_is_advisory():
    async def run():
        redis = AsyncMock()
        for method in (redis.get, redis.set, redis.delete):
            method.side_effect = ConnectionError("offline")
        cache = RecommendationCache(redis, 10)
        assert await cache.get(uuid4(), 1) is None
        await cache.put(uuid4(), 1, ready())
        await cache.invalidate(uuid4())
    asyncio.run(run())


@pytest.fixture
def pipeline(infra):
    engine, sessions, redis, stream = infra
    with sessions.begin() as session:
        user = User(email=uuid4().hex + "@test.com", display_name="Recommendation test", password_hash="fixture")
        session.add(user)
        movies = [Movie(title=f"Candidate {i}") for i in range(4)]
        session.add_all(movies)
        session.flush()
        user_id, ids = user.id, [m.id for m in movies]
    settings = get_settings().model_copy(update={"recommendation_batch_seconds": 0})
    worker = RecommendationWorker(sessions, redis, settings)
    yield sessions, redis, stream, user_id, ids, worker
    redis.delete(cache_key(user_id))


def schedule(sessions, user_id, seconds=0):
    with sessions.begin() as session:
        session.execute(schedule_statement(user_id, seconds))


def test_event_to_persisted_recommendations_and_dedup(pipeline):
    sessions, redis, stream, user, movies, worker = pipeline
    with sessions.begin() as session:
        session.add(Rating(user_id=user, movie_id=movies[0], value=5))
        event = new_event(event_type="movie.rated", aggregate_type="user_interactions",
            aggregate_id=str(user), aggregate_version=1, user_id=user,
            payload={"user_id": str(user), "movie_id": movies[0], "value": "5"})
        session.add(event)
    publisher = OutboxPublisher(sessions, redis, stream)
    assert publisher.publish_one()
    consumer = EventConsumer(sessions, redis, "recommendation-test", stream=stream)
    consumer.poll()
    publisher.replay(event.id)
    consumer.poll()
    with sessions.begin() as session:
        job = session.get(RecommendationJob, user)
        assert job.revision == 1
        job.due_at = datetime.now(timezone.utc)
    redis.set(cache_key(user), "obsolete")
    assert worker.run_one()
    assert redis.get(cache_key(user)) is None
    with sessions() as session:
        rows = list(session.scalars(select(Recommendation).where(Recommendation.user_id == user)))
        assert {r.movie_id for r in rows} == set(movies[1:])
        job = session.get(RecommendationJob, user)
        assert job.completed_revision == job.revision == 1
        assert job.generated_at >= job.source_cutoff
        assert job.generation_seconds >= 0 and job.algorithm_version == "hybrid-cf-popularity-v1"
        assert all(r.ranking_score is not None for r in rows)


def test_batch_window_concurrent_updates_and_single_claim(pipeline):
    sessions, _, _, user, _, worker = pipeline
    schedule(sessions, user, 60)
    with sessions() as session:
        due = session.get(RecommendationJob, user).due_at
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: schedule(sessions, user, 60), range(12)))
    with sessions.begin() as session:
        job = session.get(RecommendationJob, user)
        assert job.revision == 13 and job.due_at == due
        assert worker.claim() is None
        job.due_at = datetime.now(timezone.utc)
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(lambda _: worker.claim(), range(4)))
    assert sum(claim is not None for claim in claims) == 1


def test_interaction_during_calculation_discards_stale_result(pipeline):
    sessions, _, _, user, _, worker = pipeline
    schedule(sessions, user)
    original = worker.calculate
    def racing(user_id):
        result = original(user_id)
        schedule(sessions, user_id)
        return result
    worker.calculate = racing
    assert worker.run_one()
    with sessions() as session:
        job = session.get(RecommendationJob, user)
        assert job.completed_revision == 0 and job.revision == 2
        assert job.lease_token is None
        assert list(session.scalars(select(Recommendation))) == []
    worker.calculate = original
    assert worker.run_one()
    with sessions() as session:
        assert session.get(RecommendationJob, user).completed_revision == 2


def test_continuous_interactions_do_not_spin_recalculations(pipeline):
    sessions, _, _, user, _, worker = pipeline
    worker.settings = worker.settings.model_copy(update={"recommendation_batch_seconds": 60})
    schedule(sessions, user)
    original = worker.calculate
    def racing(user_id):
        result = original(user_id)
        schedule(sessions, user_id, 60)
        return result
    worker.calculate = racing
    assert worker.run_one()
    assert not worker.run_one()
    with sessions() as session:
        job = session.get(RecommendationJob, user)
        assert job.completed_revision == 0 and job.revision == 2
        assert job.due_at > datetime.now(timezone.utc) + timedelta(seconds=50)


def test_worker_failure_preserves_results_and_retries(pipeline):
    sessions, redis, _, user, _, worker = pipeline
    schedule(sessions, user)
    assert worker.run_one()
    with sessions() as session:
        generated = session.get(RecommendationJob, user).generated_at
    schedule(sessions, user)
    original = worker.calculate
    worker.calculate = Mock(side_effect=RuntimeError("private failure detail"))
    assert worker.run_one()
    with sessions.begin() as session:
        job = session.get(RecommendationJob, user)
        assert job.last_error == "RuntimeError" and job.attempts == 1
        assert job.generated_at == generated and job.completed_revision == 1
        assert job.lease_token is None
        job.due_at = datetime.now(timezone.utc)
    worker.calculate = original
    # Cache failure after commit must not turn a successful generation into a failed job.
    worker.redis = Mock()
    worker.redis.delete.side_effect = ConnectionError("cache offline")
    assert worker.run_one()
    with sessions() as session:
        job = session.get(RecommendationJob, user)
        assert job.completed_revision == 2 and job.last_error is None
    worker.redis = redis


def test_expired_lease_fences_old_worker_and_empty_generation(pipeline):
    sessions, _, _, user, movies, worker = pipeline
    with sessions.begin() as session:
        session.add_all(Rating(user_id=user, movie_id=m, value=4) for m in movies)
    schedule(sessions, user)
    first = worker.claim()
    assert first is not None
    with sessions.begin() as session:
        session.get(RecommendationJob, user).lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert worker.run_one()
    with sessions() as session:
        job = session.get(RecommendationJob, user)
        assert job.completed_revision == 1 and job.generated_at is not None
        assert job.lease_token is None
        assert list(session.scalars(select(Recommendation))) == []


def test_replaced_worker_cannot_overwrite_new_owner(pipeline):
    sessions, redis, _, user, _, worker = pipeline
    schedule(sessions, user)
    replacement = RecommendationWorker(sessions, redis, worker.settings)
    original = worker.calculate
    committed = []
    def expired_while_calculating(user_id):
        result = original(user_id)
        with sessions.begin() as session:
            session.get(RecommendationJob, user_id).lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert replacement.run_one()
        with sessions() as session:
            committed.append(session.get(RecommendationJob, user_id).generated_at)
        return result
    worker.calculate = expired_while_calculating
    assert worker.run_one()
    with sessions() as session:
        assert session.get(RecommendationJob, user).generated_at == committed[0]
    assert worker.metrics["generated_total"] == 0


def test_hybrid_result_persistence(pipeline):
    sessions, _, _, user, movies, worker = pipeline
    with sessions.begin() as session:
        peers = [User(email=uuid4().hex + "@test.com", display_name="Peer", password_hash="fixture") for _ in range(3)]
        session.add_all(peers)
        session.flush()
        session.add_all(Rating(user_id=user, movie_id=m, value=v) for m, v in zip(movies, [2, 4, 5]))
        for peer in peers:
            session.add_all(Rating(user_id=peer.id, movie_id=m, value=v) for m, v in zip(movies, [2, 4, 5, 4]))
    schedule(sessions, user)
    assert worker.run_one()
    with sessions() as session:
        result = session.scalar(select(Recommendation).where(Recommendation.user_id == user))
        assert result.method == "hybrid" and result.movie_id == movies[3]
        assert result.predicted_rating is not None and result.popularity_score is not None
        assert 0 <= result.ranking_score <= 1


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="Requires PostgreSQL/Redis")
def test_refresh_api_cache_fallback_and_live_rated_filter(client, database):
    email, registered = register(client)
    user = UUID(registered["id"])
    headers = auth(login(client, email)["access_token"])
    settings = get_settings().model_copy(update={"recommendation_batch_seconds": 0})
    sessions = sessionmaker(database, expire_on_commit=False)
    with sessions.begin() as session:
        session.execute(delete(RecommendationJob))
        session.add_all([Movie(title="API recommendation one"), Movie(title="API recommendation two")])
    assert client.get("/api/v1/recommendations/me").status_code == 401
    assert client.post("/api/v1/recommendations/refresh").status_code == 401
    fallback = client.get("/api/v1/recommendations/me", headers=headers)
    assert fallback.status_code == 200 and fallback.json()["data"]["status"] == "unavailable"
    assert fallback.json()["data"]["fallback"]
    response = client.post("/api/v1/recommendations/refresh", headers=headers)
    assert response.status_code == 202 and response.json()["data"]["status"] == "scheduled"
    assert response.headers["location"] == "/api/v1/recommendations/me"
    with sessions.begin() as session:
        session.get(RecommendationJob, user).due_at = datetime.now(timezone.utc)
    from app.core.redis import create_redis_client
    redis = create_redis_client(settings)
    try:
        worker = RecommendationWorker(sessions, redis, settings)
        assert worker.run_one()
        first = client.get("/api/v1/recommendations/me", headers=headers).json()["data"]
        assert first["status"] == "ready" and first["generated_at"]
        assert redis.ttl(cache_key(user)) > 0
        assert client.get("/api/v1/recommendations/me", headers=headers).json()["data"] == first
        movie = first["items"][0]["movie_id"]
        assert client.post("/api/v1/interactions/rating", headers=headers,
            json={"movie_id": movie, "value": 5}).status_code == 201
        filtered = client.get("/api/v1/recommendations/me", headers=headers).json()["data"]
        assert movie not in [item["movie_id"] for item in filtered["items"]]
        redis.set(cache_key(user), "broken")
        assert client.get("/api/v1/recommendations/me", headers=headers).status_code == 200
        from app.core.runtime import get_redis
        offline = AsyncMock()
        offline.get.side_effect = ConnectionError("offline")
        offline.set.side_effect = ConnectionError("offline")
        offline.delete.side_effect = ConnectionError("offline")
        client.app.dependency_overrides[get_redis] = lambda: offline
        try:
            recovered = client.get("/api/v1/recommendations/me", headers=headers)
            assert recovered.status_code == 200 and recovered.json()["data"]["generated_at"] == first["generated_at"]
        finally:
            client.app.dependency_overrides.pop(get_redis)
        # Event-driven invalidation bypasses an already populated Redis entry.
        stream = "test:recommendations:" + uuid4().hex
        try:
            assert OutboxPublisher(sessions, redis, stream).publish_one()
            EventConsumer(sessions, redis, "api-test", stream=stream).poll()
            invalidated = client.get("/api/v1/recommendations/me", headers=headers).json()["data"]
            assert invalidated["status"] == "stale"
            assert movie not in [item["movie_id"] for item in invalidated["items"]]
        finally:
            redis.delete(stream)
        client.app.dependency_overrides[get_redis] = lambda: offline
        try:
            assert client.post("/api/v1/recommendations/refresh", headers=headers).status_code == 202
        finally:
            client.app.dependency_overrides.pop(get_redis)
        assert client.post("/api/v1/recommendations/refresh", headers=headers).status_code == 202
        assert redis.get(cache_key(user)) is None
        stale = client.get("/api/v1/recommendations/me", headers=headers).json()["data"]
        assert stale["status"] == "stale" and stale["generated_at"] == first["generated_at"]
        assert client.get("/api/v1/recommendations/me?n=0", headers=headers).status_code == 422
    finally:
        redis.delete(cache_key(user))
        redis.close()
