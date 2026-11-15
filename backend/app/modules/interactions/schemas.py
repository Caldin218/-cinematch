from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer
from app.core.api import Pagination
from app.modules.movies.schemas import Identifier


class InteractionPage(Pagination):
    page: int = Field(default=1, ge=1, le=1000000)


class MovieInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    movie_id: Identifier


class ViewInput(MovieInput):
    request_id: UUID


class RatingValue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: Annotated[Decimal, Field(ge=Decimal("0.5"), le=Decimal("5"), max_digits=3, decimal_places=2)]


class RatingInput(RatingValue):
    movie_id: Identifier


class RatingRead(RatingValue):
    model_config = ConfigDict(from_attributes=True)
    movie_id: int
    created_at: datetime
    updated_at: datetime

    @field_serializer("value")
    def serialize_value(self, value: Decimal) -> float:
        return float(value)


class ViewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    movie_id: int
    request_id: UUID
    viewed_at: datetime


class HistoryRead(BaseModel):
    movie_id: int
    title: str
    is_active: bool
    first_viewed_at: datetime
    last_viewed_at: datetime
    view_count: int


class CollectionRead(BaseModel):
    movie_id: int
    title: str
    is_active: bool
    added_at: datetime
