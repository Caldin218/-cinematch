from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class EngineConfig:
    min_rating: float = 0.5
    max_rating: float = 5.0
    prior_count: float = 20.0
    view_weight: float = 0.1
    min_user_ratings: int = 3
    min_movie_ratings: int = 3
    min_overlap: int = 2
    similarity_shrinkage: float = 10.0
    neighbors: int = 30
    cf_weight: float = 0.7
    popularity_weight: float = 0.3

    def __post_init__(self) -> None:
        values = (self.min_rating, self.max_rating, self.prior_count, self.view_weight,
                  self.similarity_shrinkage, self.cf_weight, self.popularity_weight)
        if not all(isfinite(v) for v in values):
            raise ValueError("Parameters must be finite")
        if self.min_rating >= self.max_rating or self.prior_count <= 0:
            raise ValueError("Invalid rating bounds or prior count")
        if not 0 <= self.view_weight <= 1 or self.similarity_shrinkage < 0:
            raise ValueError("Invalid view weight or shrinkage")
        if min(self.cf_weight, self.popularity_weight) < 0 or self.cf_weight + self.popularity_weight <= 0:
            raise ValueError("Ranking weights must be nonnegative with a positive sum")
        for value in (self.min_user_ratings, self.min_movie_ratings, self.min_overlap, self.neighbors):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError("Count parameters must be positive integers")
