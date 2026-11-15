"""initial CineMatch schema

Revision ID: 0001_initial_schema
Revises: 
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Reviewed initial schema; migration definitions are independent of live models.
    op.create_table('genres',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('name = btrim(name) AND length(name) BETWEEN 1 AND 80', name=op.f('ck_genres_name_nonempty')),
    sa.CheckConstraint('updated_at >= created_at', name=op.f('ck_genres_timestamp_order')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_genres'))
    )
    op.create_index('uq_genres_name_lower', 'genres', [sa.literal_column('lower(name)')], unique=True)
    op.create_table('movies',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('synopsis', sa.Text(), nullable=True),
    sa.Column('release_year', sa.SmallInteger(), nullable=True),
    sa.Column('runtime_minutes', sa.Integer(), nullable=True),
    sa.Column('poster_url', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('version', sa.Integer(), server_default='1', nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('length(btrim(title)) BETWEEN 1 AND 255', name=op.f('ck_movies_title_length')),
    sa.CheckConstraint('release_year BETWEEN 1888 AND 9999', name=op.f('ck_movies_release_year_range')),
    sa.CheckConstraint('runtime_minutes > 0', name=op.f('ck_movies_runtime_positive')),
    sa.CheckConstraint('updated_at >= created_at', name=op.f('ck_movies_timestamp_order')),
    sa.CheckConstraint('version > 0', name=op.f('ck_movies_version_positive')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_movies'))
    )
    op.create_index('ix_movies_active_title_prefix', 'movies', [sa.literal_column('lower(title)').label('title_lower'), 'id'], unique=False, postgresql_ops={'title_lower': 'text_pattern_ops'}, postgresql_where=sa.text('is_active'))
    op.create_index('ix_movies_active_year', 'movies', [sa.literal_column('release_year DESC NULLS LAST'), 'id'], unique=False, postgresql_where=sa.text('is_active'))
    op.create_table('outbox_events',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('event_type', sa.String(length=100), nullable=False),
    sa.Column('schema_version', sa.Integer(), server_default='1', nullable=False),
    sa.Column('aggregate_type', sa.String(length=50), nullable=False),
    sa.Column('aggregate_id', sa.String(length=200), nullable=False),
    sa.Column('aggregate_version', sa.BigInteger(), nullable=False),
    sa.Column('payload', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('publish_attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.CheckConstraint("jsonb_typeof(payload) = 'object'", name=op.f('ck_outbox_events_payload_object')),
    sa.CheckConstraint('length(btrim(aggregate_type)) > 0 AND length(btrim(aggregate_id)) > 0', name=op.f('ck_outbox_events_aggregate_nonempty')),
    sa.CheckConstraint('length(btrim(event_type)) > 0', name=op.f('ck_outbox_events_event_type_nonempty')),
    sa.CheckConstraint('publish_attempts >= 0', name=op.f('ck_outbox_events_attempts_nonnegative')),
    sa.CheckConstraint('published_at IS NULL OR published_at >= occurred_at', name=op.f('ck_outbox_events_published_order')),
    sa.CheckConstraint('schema_version > 0 AND aggregate_version > 0', name=op.f('ck_outbox_events_versions_positive')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_outbox_events'))
    )
    op.create_index('ix_outbox_events_aggregate', 'outbox_events', ['aggregate_type', 'aggregate_id', 'aggregate_version'], unique=False)
    op.create_index('ix_outbox_events_occurred', 'outbox_events', ['occurred_at', 'id'], unique=False)
    op.create_index('ix_outbox_events_pending', 'outbox_events', ['next_attempt_at', 'occurred_at', 'id'], unique=False, postgresql_where=sa.text('published_at IS NULL'))
    op.create_table('users',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('password_hash', sa.Text(), nullable=False),
    sa.Column('display_name', sa.String(length=100), nullable=False),
    sa.Column('role', sa.String(length=16), server_default='USER', nullable=False),
    sa.Column('status', sa.String(length=16), server_default='active', nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('USER', 'ADMIN')", name=op.f('ck_users_role_allowed')),
    sa.CheckConstraint("status IN ('active', 'suspended')", name=op.f('ck_users_status_allowed')),
    sa.CheckConstraint('email = lower(btrim(email)) AND length(email) BETWEEN 3 AND 320', name=op.f('ck_users_email_normalized')),
    sa.CheckConstraint('length(btrim(display_name)) BETWEEN 1 AND 100', name=op.f('ck_users_display_name_length')),
    sa.CheckConstraint('length(password_hash) > 0', name=op.f('ck_users_password_hash_nonempty')),
    sa.CheckConstraint('updated_at >= created_at', name=op.f('ck_users_timestamp_order')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('movie_genres',
    sa.Column('movie_id', sa.BigInteger(), nullable=False),
    sa.Column('genre_id', sa.BigInteger(), nullable=False),
    sa.ForeignKeyConstraint(['genre_id'], ['genres.id'], name=op.f('fk_movie_genres_genre_id_genres'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['movie_id'], ['movies.id'], name=op.f('fk_movie_genres_movie_id_movies'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('movie_id', 'genre_id', name=op.f('pk_movie_genres'))
    )
    op.create_index('ix_movie_genres_genre_movie', 'movie_genres', ['genre_id', 'movie_id'], unique=False)
    op.create_table('movie_views',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('movie_id', sa.BigInteger(), nullable=False),
    sa.Column('request_id', sa.UUID(), nullable=False),
    sa.Column('viewed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['movie_id'], ['movies.id'], name=op.f('fk_movie_views_movie_id_movies'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_movie_views_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_movie_views')),
    sa.UniqueConstraint('user_id', 'request_id', name='uq_movie_views_user_request')
    )
    op.create_index('ix_movie_views_movie_time', 'movie_views', ['movie_id', sa.literal_column('viewed_at DESC')], unique=False)
    op.create_index('ix_movie_views_time', 'movie_views', ['viewed_at'], unique=False)
    op.create_index('ix_movie_views_user_time', 'movie_views', ['user_id', sa.literal_column('viewed_at DESC'), 'id'], unique=False)
    op.create_table('processed_events',
    sa.Column('consumer_group', sa.String(length=100), nullable=False),
    sa.Column('event_id', sa.UUID(), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('length(btrim(consumer_group)) > 0', name=op.f('ck_processed_events_consumer_nonempty')),
    sa.ForeignKeyConstraint(['event_id'], ['outbox_events.id'], name=op.f('fk_processed_events_event_id_outbox_events'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('consumer_group', 'event_id', name=op.f('pk_processed_events'))
    )
    op.create_index('ix_processed_events_event', 'processed_events', ['event_id'], unique=False)
    op.create_table('ratings',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('movie_id', sa.BigInteger(), nullable=False),
    sa.Column('value', sa.SmallInteger(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('updated_at >= created_at', name=op.f('ck_ratings_timestamp_order')),
    sa.CheckConstraint('value BETWEEN 1 AND 5', name=op.f('ck_ratings_value_range')),
    sa.ForeignKeyConstraint(['movie_id'], ['movies.id'], name=op.f('fk_ratings_movie_id_movies'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_ratings_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('user_id', 'movie_id', name=op.f('pk_ratings'))
    )
    op.create_index('ix_ratings_movie_user', 'ratings', ['movie_id', 'user_id'], unique=False)
    op.create_index('ix_ratings_user_updated', 'ratings', ['user_id', sa.literal_column('updated_at DESC'), 'movie_id'], unique=False)
    op.create_table('recommendations',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('movie_id', sa.BigInteger(), nullable=False),
    sa.Column('rank', sa.Integer(), nullable=False),
    sa.Column('method', sa.String(length=24), nullable=False),
    sa.Column('predicted_rating', sa.Numeric(precision=6, scale=5), nullable=True),
    sa.Column('popularity_score', sa.Numeric(precision=6, scale=5), nullable=True),
    sa.Column('algorithm_version', sa.String(length=64), nullable=False),
    sa.Column('source_cutoff', sa.DateTime(timezone=True), nullable=False),
    sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(method = 'user_cf' AND predicted_rating BETWEEN 1 AND 5 AND predicted_rating IS NOT NULL AND popularity_score IS NULL) OR (method = 'popularity' AND popularity_score BETWEEN 1 AND 5 AND popularity_score IS NOT NULL AND predicted_rating IS NULL) OR (method = 'catalog_fallback' AND predicted_rating IS NULL AND popularity_score IS NULL)", name=op.f('ck_recommendations_method_score_consistent')),
    sa.CheckConstraint('generated_at >= source_cutoff', name=op.f('ck_recommendations_generation_order')),
    sa.CheckConstraint('length(btrim(algorithm_version)) > 0', name=op.f('ck_recommendations_algorithm_nonempty')),
    sa.CheckConstraint('rank > 0', name=op.f('ck_recommendations_rank_positive')),
    sa.ForeignKeyConstraint(['movie_id'], ['movies.id'], name=op.f('fk_recommendations_movie_id_movies'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_recommendations_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('user_id', 'movie_id', name=op.f('pk_recommendations')),
    sa.UniqueConstraint('user_id', 'rank', name='uq_recommendations_user_rank')
    )
    op.create_index('ix_recommendations_movie', 'recommendations', ['movie_id'], unique=False)
    op.create_table('refresh_tokens',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('family_id', sa.UUID(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name=op.f('ck_refresh_tokens_hash_format')),
    sa.CheckConstraint('consumed_at IS NULL OR consumed_at >= created_at', name=op.f('ck_refresh_tokens_consumed_order')),
    sa.CheckConstraint('expires_at > created_at', name=op.f('ck_refresh_tokens_expiry_order')),
    sa.CheckConstraint('revoked_at IS NULL OR revoked_at >= created_at', name=op.f('ck_refresh_tokens_revoked_order')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_refresh_tokens_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_refresh_tokens')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_refresh_tokens_token_hash'))
    )
    op.create_index('ix_refresh_tokens_expires', 'refresh_tokens', ['expires_at'], unique=False)
    op.create_index('ix_refresh_tokens_family', 'refresh_tokens', ['family_id'], unique=False)
    op.create_index('ix_refresh_tokens_user', 'refresh_tokens', ['user_id'], unique=False)
    op.create_table('user_favorites',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('movie_id', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['movie_id'], ['movies.id'], name=op.f('fk_user_favorites_movie_id_movies'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_favorites_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'movie_id', name=op.f('pk_user_favorites'))
    )
    op.create_index('ix_user_favorites_movie', 'user_favorites', ['movie_id'], unique=False)
    op.create_index('ix_user_favorites_user_created', 'user_favorites', ['user_id', sa.literal_column('created_at DESC'), 'movie_id'], unique=False)
    op.create_table('watchlists',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('movie_id', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['movie_id'], ['movies.id'], name=op.f('fk_watchlists_movie_id_movies'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_watchlists_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'movie_id', name=op.f('pk_watchlists'))
    )
    op.create_index('ix_watchlists_movie', 'watchlists', ['movie_id'], unique=False)
    op.create_index('ix_watchlists_user_created', 'watchlists', ['user_id', sa.literal_column('created_at DESC'), 'movie_id'], unique=False)


def downgrade() -> None:
    # Reviewed initial schema; migration definitions are independent of live models.
    op.drop_index('ix_watchlists_user_created', table_name='watchlists')
    op.drop_index('ix_watchlists_movie', table_name='watchlists')
    op.drop_table('watchlists')
    op.drop_index('ix_user_favorites_user_created', table_name='user_favorites')
    op.drop_index('ix_user_favorites_movie', table_name='user_favorites')
    op.drop_table('user_favorites')
    op.drop_index('ix_refresh_tokens_user', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_family', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_expires', table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    op.drop_index('ix_recommendations_movie', table_name='recommendations')
    op.drop_table('recommendations')
    op.drop_index('ix_ratings_user_updated', table_name='ratings')
    op.drop_index('ix_ratings_movie_user', table_name='ratings')
    op.drop_table('ratings')
    op.drop_index('ix_processed_events_event', table_name='processed_events')
    op.drop_table('processed_events')
    op.drop_index('ix_movie_views_user_time', table_name='movie_views')
    op.drop_index('ix_movie_views_time', table_name='movie_views')
    op.drop_index('ix_movie_views_movie_time', table_name='movie_views')
    op.drop_table('movie_views')
    op.drop_index('ix_movie_genres_genre_movie', table_name='movie_genres')
    op.drop_table('movie_genres')
    op.drop_table('users')
    op.drop_index('ix_outbox_events_pending', table_name='outbox_events', postgresql_where=sa.text('published_at IS NULL'))
    op.drop_index('ix_outbox_events_occurred', table_name='outbox_events')
    op.drop_index('ix_outbox_events_aggregate', table_name='outbox_events')
    op.drop_table('outbox_events')
    op.drop_index('ix_movies_active_year', table_name='movies', postgresql_where=sa.text('is_active'))
    op.drop_index('ix_movies_active_title_prefix', table_name='movies', postgresql_ops={'title_lower': 'text_pattern_ops'}, postgresql_where=sa.text('is_active'))
    op.drop_table('movies')
    op.drop_index('uq_genres_name_lower', table_name='genres')
    op.drop_table('genres')
