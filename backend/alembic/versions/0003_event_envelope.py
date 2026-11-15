"""Persist envelope identity and normalize Phase 6 event names."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0003_event_envelope"
down_revision = "0002_interactions"
branch_labels = depends_on = None


def upgrade():
    op.add_column("outbox_events", sa.Column("user_id", UUID(as_uuid=True), nullable=True))
    op.add_column("outbox_events", sa.Column("correlation_id", UUID(as_uuid=True),
        nullable=False, server_default=sa.text("gen_random_uuid()")))
    op.execute("UPDATE outbox_events SET user_id = (payload->>'user_id')::uuid "
               "WHERE aggregate_type = 'user_interactions'")
    for old, new in (("interaction.viewed", "movie.viewed"),
                     ("interaction.rated", "movie.rated"),
                     ("interaction.rating_updated", "movie.rated"),
                     ("interaction.favorites_added", "movie.favorite_added"),
                     ("interaction.favorites_removed", "movie.favorite_removed")):
        op.execute(sa.text("UPDATE outbox_events SET event_type=:new WHERE event_type=:old")
                   .bindparams(old=old, new=new))


def downgrade():
    for new, old in (("movie.viewed", "interaction.viewed"),
                     ("movie.rated", "interaction.rated"),
                     ("movie.favorite_added", "interaction.favorites_added"),
                     ("movie.favorite_removed", "interaction.favorites_removed")):
        op.execute(sa.text("UPDATE outbox_events SET event_type=:old WHERE event_type=:new")
                   .bindparams(old=old, new=new))
    op.execute("UPDATE outbox_events SET event_type='interaction.rating_updated' "
               "WHERE event_type='interaction.rated' AND payload ? 'previous_value'")
    op.drop_column("outbox_events", "correlation_id")
    op.drop_column("outbox_events", "user_id")
