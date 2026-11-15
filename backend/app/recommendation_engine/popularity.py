from math import log1p

from .data import Snapshot


def popularity_scores(data: Snapshot) -> dict[int, float]:
    """Bayesian rating estimate blended with log-normalized views, on [0, 1]."""
    c = data.config
    max_views = max(data.views.values(), default=0)
    result = {}
    for movie, row in data.items.items():
        posterior = (sum(row.values()) + c.prior_count * data.global_mean) / (len(row) + c.prior_count)
        rating_score = (posterior - c.min_rating) / (c.max_rating - c.min_rating)
        view_score = log1p(data.views.get(movie, 0)) / log1p(max_views) if max_views else 0.0
        result[movie] = (1 - c.view_weight) * rating_score + c.view_weight * view_score
    return result
