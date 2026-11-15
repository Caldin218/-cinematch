from dataclasses import replace
from math import sqrt

import pytest

from app.recommendation_engine import (
    EngineConfig,
    Rating,
    RecommendationEngine,
    Snapshot,
)
from app.recommendation_engine.evaluation import (
    evaluate,
    mae,
    precision_at_k,
    recall_at_k,
    rmse,
    temporal_split,
)
from app.recommendation_engine.loading import load_movielens_100k
from app.recommendation_engine.popularity import popularity_scores
from app.recommendation_engine.similarity import centered_cosine
from app.recommendation_engine.user_based_cf import UserBasedCF


@pytest.fixture
def data():
    config = EngineConfig(min_user_ratings=2, min_movie_ratings=2, similarity_shrinkage=0)
    return Snapshot([Rating("a", 1, 5), Rating("a", 2, 1),
                     Rating("b", 1, 5), Rating("b", 2, 1), Rating("b", 3, 5),
                     Rating("c", 1, 4), Rating("c", 2, 2), Rating("c", 3, 4)],
                    movie_ids=[1, 2, 3, 4], config=config)


def test_similarity():
    assert centered_cosine({1: 5, 2: 1}, {1: 4, 2: 2}, 3, 3, shrinkage=0) == pytest.approx(1)
    assert centered_cosine({1: 5, 2: 1}, {1: 2, 2: 4}, 3, 3, shrinkage=0) == pytest.approx(-1)
    assert centered_cosine({1: 3, 2: 3}, {1: 4, 2: 2}, 3, 3) == 0
    assert centered_cosine({1: 5}, {2: 5}, 5, 5) == 0
    assert centered_cosine({1: 5}, {1: 4}, 3, 3) == 0
    assert centered_cosine({1: 5, 2: 1}, {1: 4, 2: 2}, 3, 3) == pytest.approx(1 / 6)


def test_prediction_and_cache(data):
    cf = UserBasedCF(data)
    assert cf.predict("a", 3) == pytest.approx(4.0)
    assert cf.neighbors("a") is cf.neighbors("a")
    assert cf.predict("a", 1) is None
    assert cf.predict("a", 4) is None
    assert cf.predict("unknown", 3) is None
    assert cf.recommend("a") == [(3, pytest.approx(4.0))]
    with pytest.raises(TypeError):
        data.users["a"][1] = 1


def test_popularity_shrinkage_and_views():
    rows = [Rating(i, 1, 4) for i in range(50)] + [Rating(100, 2, 5)] + [Rating(i, 4, 2) for i in range(200, 300)]
    d = Snapshot(rows, [1, 2, 3], {3: 100}, EngineConfig(view_weight=0))
    scores = popularity_scores(d)
    assert scores[1] > scores[2]
    with_views = popularity_scores(Snapshot(rows, [1, 2, 3], {3: 100}, EngineConfig(view_weight=1)))
    assert with_views[3] == 1 and with_views[1] == 0
    assert all(0 <= score <= 1 for score in scores.values())


def test_hybrid_fallback_exclusions_and_weights(data):
    engine = RecommendationEngine(data)
    result = engine.recommend("a")
    assert {r.movie_id for r in result} == {3, 4}
    r = next(r for r in result if r.movie_id == 3)
    assert r.method == "hybrid"
    assert r.score == pytest.approx(.7 * ((4.0 - .5) / 4.5) + .3 * r.popularity_score)
    assert all(r.method == "popularity" for r in engine.recommend("new"))
    assert all(r.method == "popularity" for r in engine.recommend("a", hybrid=False))
    assert engine.recommend("a", 0) == []
    with pytest.raises(ValueError):
        engine.recommend("a", -1)
    pop_only = Snapshot([Rating(u, m, v) for u, row in data.users.items() for m, v in row.items()],
                        config=replace(data.config, cf_weight=0))
    assert all(r.score == pytest.approx(r.popularity_score)
               for r in RecommendationEngine(pop_only).recommend("a"))


def test_empty_constant_no_neighbors_and_insufficient():
    assert RecommendationEngine(Snapshot([])).recommend("a") == []
    d = Snapshot([Rating("a", 1, 3), Rating("b", 2, 4)], [3])
    assert all(r.method == "popularity" for r in RecommendationEngine(d).recommend("a"))
    assert UserBasedCF(d).neighbors("a") == ()
    constant = Snapshot([Rating(u, m, 3) for u in ("a", "b") for m in (1, 2, 3)])
    assert UserBasedCF(constant).neighbors("a") == ()
    assert RecommendationEngine(Snapshot([], [2, 1])).recommend("a")[0].movie_id == 1


@pytest.mark.parametrize("kwargs", [{"prior_count": 0}, {"neighbors": 0}, {"min_overlap": 1.5},
    {"view_weight": 2}, {"cf_weight": -1}, {"cf_weight": 0, "popularity_weight": 0},
    {"similarity_shrinkage": -1}, {"max_rating": float("nan")}])
def test_invalid_config(kwargs):
    with pytest.raises(ValueError):
        EngineConfig(**kwargs)


def test_invalid_data():
    for rows in ([Rating("a", 1, 6)], [Rating("a", 1, float("nan"))],
                 [Rating("a", 1, 3), Rating("a", 1, 4)]):
        with pytest.raises(ValueError):
            Snapshot(rows)
    with pytest.raises(ValueError):
        Snapshot([], views={1: -1})


def test_metrics():
    assert mae([1, 5], [2, 3]) == 1.5
    assert rmse([1, 5], [2, 3]) == pytest.approx(sqrt(2.5))
    assert mae([], []) is None and rmse([], []) is None
    assert precision_at_k([1, 2], {2, 3}, 4) == .25
    assert recall_at_k([1, 2], {2, 3}, 4) == .5
    assert recall_at_k([], set(), 1) == 0
    with pytest.raises(ValueError):
        mae([1], [])
    with pytest.raises(ValueError):
        precision_at_k([1, 1], {1}, 2)


def test_temporal_split_and_leakage():
    rows = [Rating("a", i, 4, t) for i, t in enumerate([3, 1, 2, 3, 4])]
    train, test = temporal_split(rows, .4)
    assert max(r.timestamp for r in train) < min(r.timestamp for r in test)
    assert len(train) + len(test) == len(rows)
    assert temporal_split(rows, .4) == (train, test)
    assert temporal_split([]) == ([], [])
    with pytest.raises(ValueError):
        evaluate(train, train)
    with pytest.raises(ValueError):
        evaluate([Rating("a", 1, 3, 2)], [Rating("a", 2, 3, 1)])
    result = evaluate([Rating("a", 1, 3, 1)], [Rating("new", 99, 5, 2)])
    assert result.mae == 2 and result.rmse == 2
    assert result.cf_coverage == 0 and result.recall_at_k == 0
    assert evaluate([], []).mae is None


def test_movielens_adapter(tmp_path):
    path = tmp_path / "u.data"
    path.write_text("1\t2\t5\t123\n2\t3\t4\t124\n", encoding="ascii")
    assert load_movielens_100k(path) == [Rating(1, 2, 5, 123), Rating(2, 3, 4, 124)]



def test_top_k_and_negative_neighbors(data):
    limited = Snapshot([Rating(u, m, v) for u, row in data.users.items() for m, v in row.items()],
                       config=replace(data.config, neighbors=1))
    cf = UserBasedCF(limited)
    assert len(cf.neighbors("a")) == 1
    assert cf.neighbors("a")[0][0] == "b"
    assert cf.predict("a", 3) == pytest.approx(13 / 3)
    negative = Snapshot([Rating("a", 1, 5), Rating("a", 2, 1),
                         Rating("b", 1, 1), Rating("b", 2, 5), Rating("b", 3, 3)],
                        config=limited.config)
    assert UserBasedCF(negative).neighbors("a") == ()


def test_database_adapter():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from app.recommendation_engine.loading import load_database

    session = AsyncMock()
    movies = MagicMock()
    movies.all.return_value = [1, 2]
    session.scalars.return_value = movies
    ratings = MagicMock()
    ratings.all.return_value = [("u", 1, 4)]
    views = MagicMock()
    views.all.return_value = [(2, 5)]
    session.execute.side_effect = [ratings, views]
    data = asyncio.run(load_database(session))
    assert data.users["u"][1] == 4
    assert data.views[2] == 5
    assert set(data.items) == {1, 2}
