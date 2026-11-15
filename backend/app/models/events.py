from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        CheckConstraint("length(btrim(event_type)) > 0", name="event_type_nonempty"),
        CheckConstraint("length(btrim(aggregate_type)) > 0 AND length(btrim(aggregate_id)) > 0", name="aggregate_nonempty"),
        CheckConstraint("schema_version > 0 AND aggregate_version > 0", name="versions_positive"),
        CheckConstraint("publish_attempts >= 0", name="attempts_nonnegative"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="payload_object"),
        CheckConstraint("published_at IS NULL OR published_at >= occurred_at", name="published_order"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    aggregate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(200), nullable=False)
    aggregate_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB(none_as_null=True), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publish_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


Index("ix_outbox_events_pending", OutboxEvent.next_attempt_at, OutboxEvent.occurred_at, OutboxEvent.id,
      postgresql_where=OutboxEvent.published_at.is_(None))
Index("ix_outbox_events_aggregate", OutboxEvent.aggregate_type, OutboxEvent.aggregate_id, OutboxEvent.aggregate_version)
Index("ix_outbox_events_occurred", OutboxEvent.occurred_at, OutboxEvent.id)


class ProcessedEvent(Base):
    __tablename__ = "processed_events"
    __table_args__ = (CheckConstraint("length(btrim(consumer_group)) > 0", name="consumer_nonempty"),)

    consumer_group: Mapped[str] = mapped_column(String(100), primary_key=True)
    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("outbox_events.id", ondelete="RESTRICT"), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


Index("ix_processed_events_event", ProcessedEvent.event_id)
