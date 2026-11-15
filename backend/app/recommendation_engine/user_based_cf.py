from collections.abc import Mapping

from .data import Snapshot, UserId
from .similarity import centered_cosine


class UserBasedCF:
    def __init__(self, data: Snapshot):
        self.data = data
        self._neighbors: dict[UserId, tuple[tuple[UserId, float], ...]] = {}

    def neighbors(self, user: UserId) -> tuple[tuple[UserId, float], ...]:
        if user in self._neighbors:
            return self._neighbors[user]
        d, c = self.data, self.data.config
        row: Mapping[int, float] = d.users.get(user, {})
        if len(row) < c.min_user_ratings:
            return ()
        # Inverted index avoids comparing users who share no ratings.
        candidates = {other for movie in row for other in d.items[movie] if other != user}
        scores = []
        for other in candidates:
            if len(d.users[other]) < c.min_user_ratings:
                continue
            score = centered_cosine(row, d.users[other], d.means[user], d.means[other],
                                    c.min_overlap, c.similarity_shrinkage)
            if score > 0:
                scores.append((other, score))
        scores.sort(key=lambda pair: (-pair[1], str(pair[0])))
        result = tuple(scores[:c.neighbors])
        self._neighbors[user] = result
        return result

    def predict(self, user: UserId, movie: int) -> float | None:
        d, c = self.data, self.data.config
        if movie in d.users.get(user, {}) or len(d.items.get(movie, {})) < c.min_movie_ratings:
            return None
        numerator = denominator = 0.0
        for other, similarity in self.neighbors(user):
            if movie in d.users[other]:
                numerator += similarity * (d.users[other][movie] - d.means[other])
                denominator += similarity
        if denominator == 0:
            return None
        return max(c.min_rating, min(c.max_rating, d.means[user] + numerator / denominator))

    def recommend(self, user: UserId, n: int = 10) -> list[tuple[int, float]]:
        if n < 0:
            raise ValueError("n must be nonnegative")
        predictions = [(movie, score) for movie in self.data.items
                       if (score := self.predict(user, movie)) is not None]
        return sorted(predictions, key=lambda pair: (-pair[1], pair[0]))[:n]
