"""Real PostgreSQL schema checks; never migrate or truncate the configured database."""

import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import BigInteger, DateTime, create_engine, delete, func, inspect, insert, select, text, update
from sqlalchemy.dialects.postgresql import UUID as PGUUID, insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.core.config import get_settings
from app.core.database import Base

TABLES = {
    "users", "movies", "genres", "movie_genres", "ratings", "movie_views",
    "user_favorites", "watchlists", "outbox_events", "processed_events",
    "recommendations", "recommendation_jobs", "refresh_tokens",
}
INDEXES = {
    "uq_genres_name_lower", "ix_movies_active_year", "ix_movies_active_title_prefix",
    "ix_movie_genres_genre_movie", "ix_ratings_movie_user", "ix_ratings_user_updated",
    "ix_movie_views_user_time", "ix_movie_views_movie_time", "ix_movie_views_time",
    "ix_user_favorites_user_created", "ix_user_favorites_movie",
    "ix_watchlists_user_created", "ix_watchlists_movie", "ix_outbox_events_pending",
    "ix_outbox_events_aggregate", "ix_outbox_events_occurred", "ix_processed_events_event",
    "ix_recommendations_movie", "ix_refresh_tokens_user", "ix_refresh_tokens_family",
    "ix_refresh_tokens_expires",
    "ix_recommendation_jobs_due",
}
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="Set RUN_INTEGRATION=1; requires PostgreSQL CREATEDB"),
]


def alembic_config(connection):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


@contextmanager
def temporary_database():
    settings = get_settings()
    # Identifier is generated here, never accepted from environment/user input.
    name = "cinematch_schema_" + uuid4().hex
    assert name.startswith("cinematch_schema_") and len(name) == 49
    admin = create_engine(settings.database_url.set(database="postgres"),
                          isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
    engine = None
    created = False
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
            created = True
        engine = create_engine(settings.database_url.set(database=name),
                               connect_args={"connect_timeout": 3})
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            # Only remove the database successfully created by this invocation.
            with admin.connect() as connection:
                connection.execute(text(f'DROP DATABASE "{name}"'))
        admin.dispose()


@pytest.fixture(scope="module")
def migrated_engine():
    with temporary_database() as engine:
        assert inspect(engine).get_table_names() == []
        with engine.connect() as connection:
            command.upgrade(alembic_config(connection), "head")
        yield engine


@pytest.fixture
def db(migrated_engine):
    with migrated_engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()


@pytest.fixture
def entities(db):
    user = db.execute(insert(models.User).values(
        email="schema-test@example.com", display_name="Schema test", password_hash="test-hash-only",
    ).returning(models.User.id)).scalar_one()
    movie = db.execute(insert(models.Movie).values(title="Schema test", release_year=2026).returning(models.Movie.id)).scalar_one()
    return user, movie


def test_all_tables_types_constraints_and_indexes(migrated_engine):
    inspector = inspect(migrated_engine)
    assert set(inspector.get_table_names()) == TABLES | {"alembic_version"}
    user_columns = {c["name"]: c for c in inspector.get_columns("users")}
    assert isinstance(user_columns["id"]["type"], PGUUID)
    columns = {c["name"]: c for c in inspector.get_columns("movies")}
    assert isinstance(columns["id"]["type"], BigInteger)
    assert columns["id"]["identity"] is not None
    checks = {"users": 7, "movies": 5, "genres": 2, "ratings": 2,
              "outbox_events": 6, "processed_events": 1, "recommendations": 4, "refresh_tokens": 4}
    explicit_indexes = set()
    for table in TABLES:
        reflected = inspector.get_columns(table)
        assert {c["name"] for c in reflected} == set(Base.metadata.tables[table].c.keys())
        assert set(inspector.get_pk_constraint(table)["constrained_columns"]) == set(Base.metadata.tables[table].primary_key.columns.keys())
        assert len(inspector.get_check_constraints(table)) == checks.get(table, 0)
        assert {c["name"] for c in inspector.get_check_constraints(table)} == {
            c.name for c in Base.metadata.tables[table].constraints if c.__class__.__name__ == "CheckConstraint"
        }
        for column in reflected:
            if isinstance(column["type"], DateTime):
                assert column["type"].timezone is True
        for index in inspector.get_indexes(table):
            if not index.get("duplicates_constraint"):
                explicit_indexes.add(index["name"])
        for foreign_key in inspector.get_foreign_keys(table):
            assert foreign_key["name"]
            assert foreign_key["options"]["ondelete"] in {"RESTRICT", "CASCADE"}
        actual_uniques = {tuple(c["column_names"]) for c in inspector.get_unique_constraints(table)}
        expected_uniques = {tuple(c.columns.keys()) for c in Base.metadata.tables[table].constraints
                            if c.__class__.__name__ == "UniqueConstraint"}
        assert actual_uniques == expected_uniques
    assert explicit_indexes == INDEXES
    with migrated_engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0004_recommendation_jobs"
        # Compare schema types, nullable flags, FKs, indexes and server defaults.
        context = MigrationContext.configure(connection, opts={"compare_server_default": True})
        assert compare_metadata(context, Base.metadata) == []
        invalid = connection.scalar(text("SELECT count(*) FROM pg_index i JOIN pg_class t ON t.oid=i.indrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='public' AND NOT i.indisvalid"))
        assert invalid == 0
        definitions = dict(connection.execute(text("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='public'")).all())
        assert "WHERE (published_at IS NULL)" in definitions["ix_outbox_events_pending"]
        assert "text_pattern_ops" in definitions["ix_movies_active_title_prefix"]
        assert "WHERE is_active" in definitions["ix_movies_active_year"]


def test_uuid_bigint_and_timezone_roundtrip(db, entities):
    user, _ = entities
    assert isinstance(user, UUID)
    big_id = 2**40
    db.execute(insert(models.Movie).values(id=big_id, title="Beyond INTEGER"))
    assert db.scalar(select(models.Movie.id).where(models.Movie.id == big_id)) == big_id
    now = datetime.now(timezone(timedelta(hours=7)))
    db.execute(update(models.User).where(models.User.id == user).values(updated_at=now))
    returned = db.scalar(select(models.User.updated_at).where(models.User.id == user))
    assert returned.tzinfo is not None and returned == now


@pytest.mark.parametrize("values", [
    {"email": "UPPER@example.com"}, {"email": " spaced@example.com"},
    {"display_name": " "}, {"password_hash": ""}, {"role": "ROOT"}, {"status": "deleted"},
    {"interaction_version": -1},
])
def test_user_checks(db, values):
    data = {"email": "valid@example.com", "display_name": "Valid", "password_hash": "test-hash"} | values
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(insert(models.User).values(**data))


def test_email_and_genre_uniqueness(db, entities):
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(insert(models.User).values(email="schema-test@example.com", display_name="Duplicate", password_hash="test-hash"))
    db.execute(insert(models.Genre).values(name="Drama"))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(insert(models.Genre).values(name="drama"))


@pytest.mark.parametrize("values", [{"title": " "}, {"release_year": 1887}, {"runtime_minutes": 0}, {"version": 0}])
def test_movie_checks(db, values):
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(insert(models.Movie).values(**({"title": "Valid"} | values)))


def test_rating_update_upsert_and_bounds(db, entities):
    user, movie = entities
    statement = pg_insert(models.Rating).values(user_id=user, movie_id=movie, value=3)
    db.execute(statement)
    created = db.scalar(select(models.Rating.created_at))
    db.execute(statement.on_conflict_do_update(
        index_elements=[models.Rating.user_id, models.Rating.movie_id],
        set_={"value": 5, "updated_at": func.now()},
    ))
    assert db.scalar(select(func.count()).select_from(models.Rating)) == 1
    assert db.scalar(select(models.Rating.value)) == 5
    assert db.scalar(select(models.Rating.created_at)) == created
    for value in (0, 6):
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(update(models.Rating).values(value=value))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(insert(models.Rating).values(user_id=user, movie_id=movie, value=2))


@pytest.mark.parametrize("model", [models.UserFavorite, models.Watchlist, models.MovieGenre])
def test_collection_and_join_uniqueness(db, entities, model):
    user, movie = entities
    if model is models.MovieGenre:
        genre = db.execute(insert(models.Genre).values(name="Unique genre").returning(models.Genre.id)).scalar_one()
        values = {"movie_id": movie, "genre_id": genre}
    else:
        values = {"user_id": user, "movie_id": movie}
    db.execute(insert(model).values(**values))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(insert(model).values(**values))


def test_view_request_deduplication(db, entities):
    user, movie = entities
    request_id = uuid4()
    values = {"user_id": user, "movie_id": movie, "request_id": request_id}
    db.execute(insert(models.MovieView).values(**values))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(insert(models.MovieView).values(**values))
    db.execute(insert(models.MovieView).values(**(values | {"request_id": uuid4()})))
    assert db.scalar(select(func.count()).select_from(models.MovieView)) == 2


def event_values():
    return {"event_type": "rating.changed", "aggregate_type": "user_movie", "aggregate_id": "test-user:1",
            "aggregate_version": 1, "payload": {"rating": 4}}


def test_processed_event_idempotency_and_outbox_retention(db):
    event = db.execute(insert(models.OutboxEvent).values(**event_values()).returning(models.OutboxEvent.id)).scalar_one()
    receipt = {"event_id": event, "consumer_group": "derived-state-v1"}
    db.execute(insert(models.ProcessedEvent).values(**receipt))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(insert(models.ProcessedEvent).values(**receipt))
    db.execute(insert(models.ProcessedEvent).values(**(receipt | {"consumer_group": "another-consumer"})))
    assert db.scalar(select(func.count()).select_from(models.ProcessedEvent)) == 2
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(delete(models.OutboxEvent).where(models.OutboxEvent.id == event))


def test_receipt_and_effect_rollback_then_safe_retry(db, entities):
    user, movie = entities
    event = db.execute(insert(models.OutboxEvent).values(**event_values()).returning(models.OutboxEvent.id)).scalar_one()
    receipt = {"event_id": event, "consumer_group": "derived-state-v1"}
    with pytest.raises(RuntimeError), db.begin_nested():
        db.execute(insert(models.ProcessedEvent).values(**receipt))
        db.execute(insert(models.UserFavorite).values(user_id=user, movie_id=movie))
        raise RuntimeError("simulated handler failure")
    assert db.scalar(select(func.count()).select_from(models.ProcessedEvent)) == 0
    assert db.scalar(select(func.count()).select_from(models.UserFavorite)) == 0
    db.execute(insert(models.ProcessedEvent).values(**receipt))
    db.execute(insert(models.UserFavorite).values(user_id=user, movie_id=movie))
    duplicate = pg_insert(models.ProcessedEvent).values(**receipt).on_conflict_do_nothing().returning(models.ProcessedEvent.event_id)
    assert db.execute(duplicate).scalar_one_or_none() is None
    assert db.scalar(select(func.count()).select_from(models.UserFavorite)) == 1


@pytest.mark.parametrize("values", [
    {"payload": []}, {"payload": None}, {"payload": "string"},
    {"schema_version": 0}, {"aggregate_version": 0}, {"publish_attempts": -1},
    {"event_type": " "}, {"aggregate_id": ""},
    {"published_at": datetime(2000, 1, 1, tzinfo=timezone.utc)},
])
def test_outbox_checks(db, values):
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(insert(models.OutboxEvent).values(**(event_values() | values)))


def test_business_state_and_event_rollback_together(db, entities):
    user, movie = entities
    with pytest.raises(RuntimeError), db.begin_nested():
        db.execute(insert(models.Rating).values(user_id=user, movie_id=movie, value=4))
        db.execute(insert(models.OutboxEvent).values(**event_values()))
        raise RuntimeError("simulate aborted business transaction")
    assert db.scalar(select(func.count()).select_from(models.Rating)) == 0
    assert db.scalar(select(func.count()).select_from(models.OutboxEvent)) == 0


def recommendation_values(user, movie, **overrides):
    return {"user_id": user, "movie_id": movie, "rank": 1, "method": "catalog_fallback",
            "algorithm_version": "schema-test-only", "source_cutoff": datetime(2000, 1, 1, tzinfo=timezone.utc)} | overrides


@pytest.mark.parametrize("values", [
    {"rank": 0}, {"method": "unknown"}, {"method": "user_cf"}, {"method": "popularity"},
    {"predicted_rating": 4}, {"method": "user_cf", "predicted_rating": 6},
    {"method": "popularity", "popularity_score": 0},
    {"algorithm_version": ""}, {"source_cutoff": datetime(9999, 1, 1, tzinfo=timezone.utc)},
])
def test_recommendation_checks(db, entities, values):
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(insert(models.Recommendation).values(**recommendation_values(*entities, **values)))


def test_recommendation_atomic_replacement_and_unique_rank(db, entities):
    user, movie = entities
    other = db.execute(insert(models.Movie).values(title="Replacement").returning(models.Movie.id)).scalar_one()
    db.execute(insert(models.Recommendation).values(**recommendation_values(user, movie)))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(insert(models.Recommendation).values(**recommendation_values(user, other)))
    with pytest.raises(RuntimeError), db.begin_nested():
        db.execute(delete(models.Recommendation).where(models.Recommendation.user_id == user))
        db.execute(insert(models.Recommendation).values(**recommendation_values(user, other)))
        raise RuntimeError("failed replacement")
    assert db.scalar(select(models.Recommendation.movie_id)) == movie
    db.execute(delete(models.Recommendation).where(models.Recommendation.user_id == user))
    db.execute(insert(models.Recommendation).values(**recommendation_values(user, other)))
    assert db.scalar(select(models.Recommendation.movie_id)) == other


def token_values(user, **overrides):
    return {"user_id": user, "family_id": uuid4(), "token_hash": "a" * 64,
            "expires_at": datetime(2099, 1, 1, tzinfo=timezone.utc)} | overrides


@pytest.mark.parametrize("values", [
    {"token_hash": "raw-token"}, {"expires_at": datetime(2000, 1, 1, tzinfo=timezone.utc)},
    {"consumed_at": datetime(2000, 1, 1, tzinfo=timezone.utc)},
    {"revoked_at": datetime(2000, 1, 1, tzinfo=timezone.utc)},
])
def test_refresh_checks(db, entities, values):
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(insert(models.RefreshToken).values(**token_values(entities[0], **values)))


def test_refresh_hash_unique(db, entities):
    db.execute(insert(models.RefreshToken).values(**token_values(entities[0])))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(insert(models.RefreshToken).values(**token_values(entities[0])))


def test_foreign_key_rejects_missing_parent(db, entities):
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(insert(models.Rating).values(user_id=uuid4(), movie_id=entities[1], value=4))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(insert(models.Rating).values(user_id=entities[0], movie_id=2**62, value=4))


def test_restrict_historical_deletion(db, entities):
    user, movie = entities
    db.execute(insert(models.Rating).values(user_id=user, movie_id=movie, value=4))
    for statement in (delete(models.User).where(models.User.id == user), delete(models.Movie).where(models.Movie.id == movie)):
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(statement)


def test_cascade_disposable_collections_and_restrict_genre(db, entities):
    user, movie = entities
    genre = db.execute(insert(models.Genre).values(name="Linked").returning(models.Genre.id)).scalar_one()
    db.execute(insert(models.MovieGenre).values(movie_id=movie, genre_id=genre))
    db.execute(insert(models.UserFavorite).values(user_id=user, movie_id=movie))
    db.execute(insert(models.Watchlist).values(user_id=user, movie_id=movie))
    db.execute(insert(models.RefreshToken).values(**token_values(user)))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(delete(models.Genre).where(models.Genre.id == genre))
    db.execute(delete(models.Movie).where(models.Movie.id == movie))
    for model in (models.MovieGenre, models.UserFavorite, models.Watchlist):
        assert db.scalar(select(func.count()).select_from(model)) == 0
    db.execute(delete(models.User).where(models.User.id == user))
    assert db.scalar(select(func.count()).select_from(models.RefreshToken)) == 0


def test_orm_mapping_persists_model(db):
    with Session(bind=db, join_transaction_mode="create_savepoint") as session:
        user = models.User(email="orm@example.com", display_name="ORM", password_hash="test-hash")
        session.add(user)
        session.flush()
        assert isinstance(user.id, UUID)
        assert user.created_at.tzinfo is not None
        user.display_name = "Updated"
        session.flush()
        assert user.updated_at >= user.created_at


def test_empty_upgrade_check_downgrade_reupgrade():
    with temporary_database() as engine:
        assert inspect(engine).get_table_names() == []
        with engine.connect() as connection:
            config = alembic_config(connection)
            command.upgrade(config, "head")
            command.upgrade(config, "head")  # Already at head is a no-op.
            command.check(config)
            command.downgrade(config, "base")
            assert set(inspect(connection).get_table_names()) <= {"alembic_version"}
            connection.commit()
            command.upgrade(config, "head")
            command.check(config)
        assert set(inspect(engine).get_table_names()) == TABLES | {"alembic_version"}
