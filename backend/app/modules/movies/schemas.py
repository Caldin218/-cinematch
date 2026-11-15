from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.core.api import Pagination

Identifier = Annotated[int, Field(gt=0, le=9223372036854775807)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Year = Annotated[int, Field(ge=1888, le=9999)]

class CatalogQuery(Pagination):
    page: int = Field(default=1, ge=1, le=1000000)
    q: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)] | None = None
    genre_id: Identifier | None = None
    release_year: Year | None = None
    min_rating: float | None = Field(default=None, ge=0, le=5)
    max_rating: float | None = Field(default=None, ge=0, le=5)
    sort: Literal["popularity", "rating", "release_year", "match"] = "popularity"

    @model_validator(mode="after")
    def rating_bounds(self) -> "CatalogQuery":
        if self.min_rating is not None and self.max_rating is not None and self.min_rating > self.max_rating:
            raise ValueError("min_rating must not exceed max_rating")
        return self

class MovieCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title
    original_title: Title | None = None
    trailer_youtube_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{11}$")
    synopsis: str | None = Field(default=None, max_length=20000)
    release_year: Year | None = None
    runtime_minutes: int | None = Field(default=None, gt=0, le=2147483647)
    poster_url: HttpUrl | None = None
    genre_ids: list[Identifier] = Field(default_factory=list, max_length=100)

    @field_validator("genre_ids")
    @classmethod
    def unique_genres(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("Duplicate genres")
        return value

class MovieUpdate(MovieCreate):
    title: Title | None = None

    @model_validator(mode="after")
    def valid_patch(self) -> "MovieUpdate":
        if not self.model_fields_set or ("title" in self.model_fields_set and self.title is None):
            raise ValueError("Provide a nonempty patch and non-null title")
        if "genre_ids" in self.model_fields_set and self.genre_ids is None:
            raise ValueError("genre_ids cannot be null")
        return self

class GenreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str

class MovieRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    original_title: str | None = None
    trailer_youtube_id: str | None = None
    comment_count: int = 0
    synopsis: str | None
    release_year: int | None
    runtime_minutes: int | None
    poster_url: str | None
    version: int
    genres: list[GenreRead]
    average_rating: float | None
    rating_count: int
    popularity: int
