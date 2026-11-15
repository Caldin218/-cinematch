from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType

from .config import EngineConfig

UserId = Hashable


@dataclass(frozen=True)
class Rating:
    user_id: UserId
    movie_id: int
    value: float
    timestamp: int = 0


class Snapshot:
    """Immutable sparse user/item indexes. Duplicate user/movie pairs are rejected."""

    def __init__(self, ratings: Iterable[Rating], movie_ids: Iterable[int] = (),
                 views: Mapping[int, int] | None = None, config: EngineConfig | None = None):
        self.config = config or EngineConfig()
        users: dict[UserId, dict[int, float]] = {}
        items: dict[int, dict[UserId, float]] = {m: {} for m in movie_ids}
        for r in ratings:
            if not isfinite(r.value) or not self.config.min_rating <= r.value <= self.config.max_rating:
                raise ValueError("Rating outside configured bounds")
            row = users.setdefault(r.user_id, {})
            if r.movie_id in row:
                raise ValueError("Duplicate user/movie rating")
            row[r.movie_id] = r.value
            items.setdefault(r.movie_id, {})[r.user_id] = r.value
        counts = dict(views or {})
        if any(not isinstance(v, int) or v < 0 for v in counts.values()):
            raise ValueError("View counts must be nonnegative integers")
        for movie in counts:
            items.setdefault(movie, {})
        self.users = MappingProxyType({u: MappingProxyType(row) for u, row in users.items()})
        self.items = MappingProxyType({m: MappingProxyType(row) for m, row in items.items()})
        self.views = MappingProxyType(counts)
        self.means = MappingProxyType({u: sum(row.values()) / len(row) for u, row in users.items()})
        total = sum(len(row) for row in users.values())
        self.global_mean = (sum(sum(row.values()) for row in users.values()) / total if total
                            else (self.config.min_rating + self.config.max_rating) / 2)
