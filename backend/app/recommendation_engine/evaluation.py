"""Deterministic temporal evaluation. All model statistics come from train only."""
import argparse
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from math import ceil, isfinite, sqrt

from .config import EngineConfig
from .data import Rating, Snapshot, UserId
from .hybrid import RecommendationEngine
from .loading import load_movielens_100k


def mae(actual: Sequence[float], predicted: Sequence[float]) -> float | None:
    _validate_pairs(actual, predicted)
    return sum(abs(a - p) for a, p in zip(actual, predicted)) / len(actual) if actual else None


def rmse(actual: Sequence[float], predicted: Sequence[float]) -> float | None:
    _validate_pairs(actual, predicted)
    return sqrt(sum((a - p) ** 2 for a, p in zip(actual, predicted)) / len(actual)) if actual else None


def _validate_pairs(actual: Sequence[float], predicted: Sequence[float]) -> None:
    if len(actual) != len(predicted) or not all(isfinite(v) for v in (*actual, *predicted)):
        raise ValueError("Expected equally sized finite values")


def precision_at_k(recommended: Sequence[int], relevant: set[int], k: int) -> float:
    if k < 1 or len(set(recommended)) != len(recommended):
        raise ValueError("Expected positive k and unique recommendations")
    return len(set(recommended[:k]) & relevant) / k


def recall_at_k(recommended: Sequence[int], relevant: set[int], k: int) -> float:
    if k < 1 or len(set(recommended)) != len(recommended):
        raise ValueError("Expected positive k and unique recommendations")
    return len(set(recommended[:k]) & relevant) / len(relevant) if relevant else 0.0


def temporal_split(ratings: Iterable[Rating], test_fraction: float = 0.2) -> tuple[list[Rating], list[Rating]]:
    """Global chronological holdout; all ties at cutoff go to test."""
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction must be between zero and one")
    rows = list(ratings)
    Snapshot(rows)  # Reject duplicate pairs before split (including across the boundary).
    if len(rows) < 2:
        return rows, []
    rows.sort(key=lambda r: r.timestamp)
    cutoff = rows[max(1, len(rows) - ceil(len(rows) * test_fraction))].timestamp
    return ([r for r in rows if r.timestamp < cutoff], [r for r in rows if r.timestamp >= cutoff])


@dataclass(frozen=True)
class Evaluation:
    mae: float | None
    rmse: float | None
    cf_mae: float | None
    cf_rmse: float | None
    cf_coverage: float
    precision_at_k: float
    recall_at_k: float
    test_ratings: int
    ranking_users: int


def evaluate(train: Sequence[Rating], test: Sequence[Rating], *, config: EngineConfig | None = None,
             k: int = 10, relevance_threshold: float = 4.0) -> Evaluation:
    if k < 1:
        raise ValueError("k must be positive")
    if {(r.user_id, r.movie_id) for r in train} & {(r.user_id, r.movie_id) for r in test}:
        raise ValueError("Train/test user-item leakage")
    if train and test and max(r.timestamp for r in train) >= min(r.timestamp for r in test):
        raise ValueError("Train must strictly precede test")
    # No held-out catalog, views, means, counts, or similarities enter this snapshot.
    data = Snapshot(train, config=config)
    Snapshot(test, config=data.config)
    engine = RecommendationEngine(data)
    actual, predicted, cf_actual, cf_predicted = [], [], [], []
    relevant: dict[UserId, set[int]] = defaultdict(set)
    for r in test:
        prediction = engine.cf.predict(r.user_id, r.movie_id)
        actual.append(r.value)
        if prediction is not None:
            cf_actual.append(r.value)
            cf_predicted.append(prediction)
        row: Mapping[UserId, float] = data.items.get(r.movie_id, {})
        # Explicit rating-scale Bayesian fallback; normalized hybrid scores are not ratings.
        fallback = (sum(row.values()) + data.config.prior_count * data.global_mean) / (len(row) + data.config.prior_count)
        predicted.append(prediction if prediction is not None else fallback)
        if r.value >= relevance_threshold:
            relevant[r.user_id].add(r.movie_id)
    precision, recall = [], []
    for user, positives in relevant.items():
        recommendations = [r.movie_id for r in engine.recommend(user, k)]
        precision.append(precision_at_k(recommendations, positives, k))
        recall.append(recall_at_k(recommendations, positives, k))
    return Evaluation(mae(actual, predicted), rmse(actual, predicted), mae(cf_actual, cf_predicted),
                      rmse(cf_actual, cf_predicted), len(cf_actual) / len(test) if test else 0.0,
                      sum(precision) / len(precision) if precision else 0.0,
                      sum(recall) / len(recall) if recall else 0.0, len(test), len(relevant))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ratings_path", help="Path to MovieLens 100K u.data")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    args = parser.parse_args()
    train, test = temporal_split(load_movielens_100k(args.ratings_path), args.test_fraction)
    print(json.dumps(asdict(evaluate(train, test, config=EngineConfig(min_rating=1.0), k=args.k)), indent=2))


if __name__ == "__main__":
    main()
