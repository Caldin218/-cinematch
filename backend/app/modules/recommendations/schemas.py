from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")
    movie_id: Annotated[int, Field(strict=True, gt=0)]
    rank: Annotated[int, Field(strict=True, gt=0)]
    method: Literal["user_cf", "hybrid", "popularity", "catalog_fallback"]
    ranking_score: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    predicted_rating: float | None = Field(default=None, ge=0.5, le=5, allow_inf_nan=False)
    popularity_score: float | None = Field(default=None, ge=0.5, le=5, allow_inf_nan=False)

    @model_validator(mode="after")
    def scores(self):
        if (self.method == "user_cf" and (self.predicted_rating is None or self.popularity_score is not None)
                or self.method == "popularity" and (self.popularity_score is None or self.predicted_rating is not None)
                or self.method == "hybrid" and (self.popularity_score is None or self.predicted_rating is None or self.ranking_score is None)
                or self.method == "catalog_fallback" and (self.predicted_rating is not None or self.popularity_score is not None)):
            raise ValueError("Inconsistent recommendation scores")
        return self


class RecommendationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[Item] = Field(max_length=100)
    generated_at: AwareDatetime | None = None
    source_cutoff: AwareDatetime | None = None
    algorithm_version: str = Field(min_length=1, max_length=64)
    generation_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    status: Literal["ready", "stale", "unavailable"]
    fallback: str | None = None


class CachedRecommendations(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    user_id: UUID
    revision: Annotated[int, Field(strict=True, ge=1)]
    result: RecommendationRead

    @model_validator(mode="after")
    def valid_result(self):
        result = self.result
        if (result.status != "ready" or result.generated_at is None or result.source_cutoff is None
                or result.generated_at < result.source_cutoff or result.generation_seconds is None
                or len({item.movie_id for item in result.items}) != len(result.items)
                or [item.rank for item in result.items] != list(range(1, len(result.items) + 1))):
            raise ValueError("Invalid cached generation")
        return self


class RefreshRead(BaseModel):
    status: Literal["scheduled"] = "scheduled"
    scheduled_for: AwareDatetime
