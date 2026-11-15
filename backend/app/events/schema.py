from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    movie_id: Annotated[int, Field(strict=True, gt=0)]


class InteractionPayload(Payload):
    user_id: UUID


class ViewedPayload(InteractionPayload):
    request_id: UUID
    view_id: Annotated[int, Field(strict=True, gt=0)]


Score = Annotated[Decimal, Field(ge=Decimal("0.5"), le=5, decimal_places=2, allow_inf_nan=False)]


class RatedPayload(InteractionPayload):
    value: Score
    previous_value: Score | None = None


class CatalogPayload(Payload):
    version: Annotated[int, Field(strict=True, gt=0)]


PAYLOADS = {
    "movie.viewed": ViewedPayload,
    "movie.rated": RatedPayload,
    "movie.favorite_added": InteractionPayload,
    "movie.favorite_removed": InteractionPayload,
    "interaction.watchlist_added": InteractionPayload,
    "interaction.watchlist_removed": InteractionPayload,
    "movie.created": CatalogPayload,
    "movie.updated": CatalogPayload,
    "movie.deleted": CatalogPayload,
}


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    event_type: str
    aggregate_id: str = Field(min_length=1, max_length=200)
    user_id: UUID | None
    payload: dict
    occurred_at: AwareDatetime
    schema_version: Literal[1]
    correlation_id: UUID

    @field_validator("schema_version", mode="before")
    @classmethod
    def strict_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("Unsupported schema version")
        return value

    @model_validator(mode="after")
    def validate_contract(self):
        payload_type = PAYLOADS.get(self.event_type)
        if payload_type is None:
            raise ValueError("Unsupported event type")
        parsed = payload_type.model_validate(self.payload)
        if isinstance(parsed, InteractionPayload):
            if self.user_id != parsed.user_id or self.aggregate_id != str(self.user_id):
                raise ValueError("Interaction identity mismatch")
        elif self.aggregate_id != str(parsed.movie_id):
            raise ValueError("Catalog identity mismatch")
        return self


def envelope(row):
    return EventEnvelope(event_id=row.id, event_type=row.event_type,
        aggregate_id=row.aggregate_id, user_id=row.user_id, payload=row.payload,
        occurred_at=row.occurred_at, schema_version=row.schema_version,
        correlation_id=row.correlation_id)


def new_event(**values):
    """Validate producer data before the surrounding business transaction commits."""
    from datetime import datetime, timezone
    from uuid import uuid4

    from app.core.correlation import request_id
    from app.models import OutboxEvent
    values.setdefault("id", uuid4())
    values.setdefault("occurred_at", datetime.now(timezone.utc))
    values.setdefault("schema_version", 1)
    values.setdefault("user_id", None)
    values.setdefault("correlation_id", UUID(request_id.get()) if request_id.get() else uuid4())
    row = OutboxEvent(**values)
    envelope(row)
    return row
