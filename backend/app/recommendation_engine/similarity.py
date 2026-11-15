from collections.abc import Mapping
from math import sqrt


def centered_cosine(left: Mapping[int, float], right: Mapping[int, float],
                    left_mean: float, right_mean: float, min_overlap: int = 2,
                    shrinkage: float = 10.0) -> float:
    """Pearson-style cosine on co-rated items, centered by training user means."""
    common = left.keys() & right.keys()
    if len(common) < min_overlap:
        return 0.0
    dot = sum((left[m] - left_mean) * (right[m] - right_mean) for m in common)
    norm = sqrt(sum((left[m] - left_mean) ** 2 for m in common)
                * sum((right[m] - right_mean) ** 2 for m in common))
    return dot / norm * len(common) / (len(common) + shrinkage) if norm else 0.0
