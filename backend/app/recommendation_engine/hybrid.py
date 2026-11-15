from dataclasses import dataclass

from .data import Snapshot, UserId
from .popularity import popularity_scores
from .user_based_cf import UserBasedCF


@dataclass(frozen=True)
class Recommendation:
    movie_id: int
    score: float
    method: str
    predicted_rating: float | None
    popularity_score: float


class RecommendationEngine:
    def __init__(self, data: Snapshot):
        self.data = data
        self.cf = UserBasedCF(data)
        self.popularity = popularity_scores(data)

    def recommend(self, user: UserId, n: int = 10, *, hybrid: bool = True) -> list[Recommendation]:
        if n < 0:
            raise ValueError("n must be nonnegative")
        c = self.data.config
        result = []
        for movie, pop in self.popularity.items():
            if movie in self.data.users.get(user, {}):
                continue
            prediction = self.cf.predict(user, movie) if hybrid else None
            score, method = pop, "popularity"
            if prediction is not None:
                normalized = (prediction - c.min_rating) / (c.max_rating - c.min_rating)
                score = (c.cf_weight * normalized + c.popularity_weight * pop) / (c.cf_weight + c.popularity_weight)
                method = "hybrid"
            result.append(Recommendation(movie, score, method, prediction, pop))
        return sorted(result, key=lambda r: (-r.score, r.movie_id))[:n]
