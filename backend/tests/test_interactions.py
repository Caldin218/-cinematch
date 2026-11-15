import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, insert, select, update
from app.models import Movie, MovieView, OutboxEvent, Rating, User, UserFavorite, Watchlist
from test_auth import database, client, register, login, auth

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="Requires PostgreSQL/Redis")]
BASE = "/api/v1/interactions"

@pytest.fixture
def actor(client):
    email, user = register(client)
    return UUID(user["id"]), auth(login(client, email)["access_token"])

@pytest.fixture
def movies(database):
    with database.begin() as c:
        return [c.scalar(insert(Movie).values(title="Interaction " + uuid4().hex).returning(Movie.id)) for _ in range(3)]

def rows(database, model, user_id):
    with database.connect() as c:
        return c.execute(select(model).where(model.user_id == user_id)).mappings().all()

def events(database, user_id):
    with database.connect() as c:
        return c.execute(select(OutboxEvent).where(OutboxEvent.aggregate_type == "user_interactions",
            OutboxEvent.aggregate_id == str(user_id)).order_by(OutboxEvent.aggregate_version)).mappings().all()

def version(database, user_id):
    with database.connect() as c:
        return c.scalar(select(User.interaction_version).where(User.id == user_id))

def test_rating_create_duplicate_update_and_catalog(client, actor, movies, database):
    user_id, headers = actor
    movie = movies[0]
    result = client.post(BASE+"/rating", headers=headers, json={"movie_id":movie, "value":0.5})
    assert result.status_code == 201, result.text
    original = result.json()["data"]
    assert original["created_at"] == original["updated_at"]
    assert original["value"] == 0.5 and result.headers["cache-control"] == "no-store"
    assert client.post(BASE+"/rating", headers=headers, json={"movie_id":movie,"value":5}).status_code == 409
    result = client.put(BASE+f"/rating/{movie}", headers=headers, json={"value":4.25})
    assert result.status_code == 200, result.text
    changed = result.json()["data"]
    assert changed["value"] == 4.25 and changed["created_at"] == original["created_at"]
    assert changed["updated_at"] >= original["updated_at"]
    assert client.put(BASE+f"/rating/{movie}", headers=headers, json={"value":4.25}).json()["data"] == changed
    assert len(rows(database, Rating, user_id)) == 1
    emitted = events(database, user_id)
    assert [e["aggregate_version"] for e in emitted] == [1,2]
    assert [e["event_type"] for e in emitted] == ["movie.rated", "movie.rated"]
    assert Decimal(emitted[1]["payload"]["previous_value"]) == Decimal("0.5")
    detail = client.get(f"/api/v1/movies/{movie}").json()["data"]
    assert detail["average_rating"] == 4.25 and detail["rating_count"] == 1
    filtered = client.get("/api/v1/movies", params={"min_rating":4.2, "max_rating":4.3}).json()["data"]
    assert movie in [m["id"] for m in filtered["items"]]
    assert client.put(BASE+f"/rating/{movies[1]}",headers=headers,json={"value":3}).status_code == 404

@pytest.mark.parametrize("value", [0,0.49,5.01,6,-1,"NaN","Infinity",None,True,1.234])
def test_invalid_rating_values(client, actor, movies, value):
    _, headers = actor
    assert client.post(BASE+"/rating", headers=headers, json={"movie_id":movies[0],"value":value}).status_code == 422
    assert client.put(BASE+f"/rating/{movies[0]}",headers=headers,json={"value":value}).status_code == 422

def test_views_retry_conflict_history_and_deleted_movie(client, actor, movies, database):
    user_id, headers = actor
    data = {"movie_id":movies[0],"request_id":str(uuid4())}
    first = client.post(BASE+"/view",headers=headers,json=data)
    assert first.status_code == 200, first.text
    assert client.post(BASE+"/view",headers=headers,json=data).json() == first.json()
    assert client.post(BASE+"/view",headers=headers,json=data | {"movie_id":movies[1]}).status_code == 409
    assert client.post(BASE+"/view",headers=headers,json=data | {"request_id":str(uuid4())}).status_code == 200
    assert client.post(BASE+"/view",headers=headers,json={"movie_id":movies[1],"request_id":str(uuid4())}).status_code == 200
    history = client.get(BASE+"/history",headers=headers, params={"page_size":1})
    assert history.headers["cache-control"] == "no-store"
    assert history.json()["data"]["total"] == 2
    assert history.json()["data"]["items"][0]["movie_id"] == movies[1]
    second = client.get(BASE+"/history",headers=headers,params={"page":2,"page_size":1}).json()["data"]["items"][0]
    assert second["movie_id"] == movies[0] and second["view_count"] == 2
    assert second["first_viewed_at"] <= second["last_viewed_at"]
    assert len(rows(database,MovieView,user_id)) == 3 and version(database,user_id) == 3
    assert len(events(database,user_id)) == 3
    with database.begin() as c:
        c.execute(update(Movie).where(Movie.id == movies[0]).values(is_active=False))
    assert client.post(BASE+"/view",headers=headers,json=data).json() == first.json()
    assert client.post(BASE+"/view",headers=headers,json=data | {"request_id":str(uuid4())}).status_code == 404
    assert client.get(BASE+"/history",headers=headers,params={"page":2,"page_size":1}).json()["data"]["items"][0]["is_active"] is False

@pytest.mark.parametrize("kind,model",[("favorites",UserFavorite),("watchlist",Watchlist)])
def test_collections_idempotency_pagination_and_removed_movies(client, actor, movies, database, kind, model):
    user_id, headers = actor
    for movie in movies[:2]:
        for _ in range(2):
            assert client.post(BASE+"/"+kind, headers=headers,json={"movie_id":movie}).status_code == 204
    assert len(rows(database,model,user_id)) == 2 and len(events(database,user_id)) == 2
    result = client.get(BASE+"/"+kind,headers=headers,params={"page_size":1}).json()["data"]
    assert result["total"] == 2 and result["items"][0]["movie_id"] == movies[1]
    assert client.get(BASE+"/"+kind,headers=headers,params={"page":2,"page_size":1}).json()["data"]["items"][0]["movie_id"] == movies[0]
    with database.begin() as c:
        c.execute(update(Movie).where(Movie.id == movies[1]).values(is_active=False))
    assert client.get(BASE+"/"+kind,headers=headers).json()["data"]["items"][0]["is_active"] is False
    assert client.post(BASE+"/"+kind,headers=headers,json={"movie_id":movies[1]}).status_code == 404
    for _ in range(2):
        assert client.delete(BASE+f"/{kind}/{movies[1]}",headers=headers).status_code == 204
    assert client.delete(BASE+f"/{kind}/9223372036854775807",headers=headers).status_code == 204
    assert len(events(database,user_id)) == 3 and version(database,user_id) == 3
    assert len(rows(database,model,user_id)) == 1

def test_ownership_and_authentication(client, actor, movies, database):
    user_id, headers = actor
    for path, data in (("view",{"movie_id":movies[0],"request_id":str(uuid4())}),
                       ("rating",{"movie_id":movies[0],"value":5}),
                       ("favorites",{"movie_id":movies[0]}),("watchlist",{"movie_id":movies[0]})):
        assert client.post(BASE+"/"+path,json=data).status_code == 401
        assert client.post(BASE+"/"+path,headers=headers,json=data).status_code in (200,201,204)
        assert client.post(BASE+"/"+path,headers=headers,json=data | {"user_id":str(uuid4())}).status_code == 422
    email, _ = register(client)
    other = auth(login(client,email)["access_token"])
    for path in ("history","favorites","watchlist"):
        assert client.get(BASE+"/"+path).status_code == 401
        assert client.get(BASE+"/"+path,headers=other).json()["data"]["total"] == 0
        assert client.get(BASE+"/"+path,headers=headers).json()["data"]["total"] == 1
    assert client.put(BASE+f"/rating/{movies[0]}",headers=other,json={"value":2}).status_code == 404
    assert client.put(BASE+f"/rating/{movies[0]}",json={"value":2}).status_code == 401
    for path in ("favorites","watchlist"):
        assert client.delete(BASE+f"/{path}/{movies[0]}").status_code == 401
        assert client.delete(BASE+f"/{path}/{movies[0]}",headers=other).status_code == 204
        assert client.get(BASE+"/"+path,headers=headers).json()["data"]["total"] == 1
    assert rows(database,Rating,user_id)[0]["value"] == 5

def test_missing_movies_ids_and_pagination(client, actor, movies, database):
    user_id, headers = actor
    for path in ("favorites","watchlist","view","rating"):
        data = {"movie_id":9223372036854775807}
        if path == "view": data["request_id"] = str(uuid4())
        if path == "rating": data["value"] = 3
        assert client.post(BASE+"/"+path,headers=headers,json=data).status_code == 404
        assert client.post(BASE+"/"+path,headers=headers,json=data | {"movie_id":0}).status_code == 422
    assert client.post(BASE+"/view",headers=headers,json={"movie_id":movies[0]}).status_code == 422
    assert client.post(BASE+"/view",headers=headers,json={"movie_id":movies[0],"request_id":"bad"}).status_code == 422
    for path in ("history","favorites","watchlist"):
        for params in ({"page":0},{"page_size":101},{"page":1000001}):
            assert client.get(BASE+"/"+path,headers=headers,params=params).status_code == 422
        assert client.get(BASE+"/"+path,headers=headers,params={"page":99}).json()["data"]["items"] == []
    assert not events(database,user_id) and version(database,user_id) == 0

@pytest.mark.parametrize("path,model",[("rating",Rating),("view",MovieView),("favorites",UserFavorite),("watchlist",Watchlist)])
def test_outbox_failure_rolls_back_state_and_sequence(client, actor, movies, database, path, model):
    user_id, headers = actor
    data = {"movie_id":movies[0]}
    if path == "rating": data["value"] = 4.5
    if path == "view": data["request_id"] = str(uuid4())
    engine = client.app.state.async_sessions.kw["bind"].sync_engine
    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO outbox_events"):
            raise RuntimeError("injected outbox failure: SECRET MUST NOT LEAK")
    event.listen(engine,"before_cursor_execute",fail)
    try:
        response = client.post(BASE+"/"+path,headers=headers,json=data)
        assert response.status_code == 500
        assert "SECRET" not in response.text
    finally:
        event.remove(engine,"before_cursor_execute",fail)
    assert not rows(database,model,user_id) and not events(database,user_id)
    assert version(database,user_id) == 0
    assert client.post(BASE+"/"+path,headers=headers,json=data).status_code in (200,201,204)
    assert len(rows(database,model,user_id)) == 1 and version(database,user_id) == 1

def test_update_and_removal_commit_failure_roll_back(client, actor, movies, database):
    user_id, headers = actor
    assert client.post(BASE+"/rating",headers=headers,json={"movie_id":movies[0],"value":3.5}).status_code == 201
    assert client.post(BASE+"/favorites",headers=headers,json={"movie_id":movies[0]}).status_code == 204
    engine = client.app.state.async_sessions.kw["bind"].sync_engine
    def fail(connection):
        raise RuntimeError("injected commit failure")
    event.listen(engine,"commit",fail)
    try:
        assert client.put(BASE+f"/rating/{movies[0]}",headers=headers,json={"value":5}).status_code == 500
        assert client.delete(BASE+f"/favorites/{movies[0]}",headers=headers).status_code == 500
    finally:
        event.remove(engine,"commit",fail)
    assert rows(database,Rating,user_id)[0]["value"] == Decimal("3.5")
    assert len(rows(database,UserFavorite,user_id)) == 1
    assert len(events(database,user_id)) == 2 and version(database,user_id) == 2


def test_concurrent_duplicate_views_ratings_and_favorites(client, actor, movies, database):
    user_id, headers = actor
    data = {"movie_id":movies[0],"request_id":str(uuid4())}
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.post(BASE+"/view",headers=headers,json=data),range(4)))
    assert all(r.status_code == 200 for r in results)
    assert all(r.json() == results[0].json() for r in results)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.post(BASE+"/rating",headers=headers,json={"movie_id":movies[0],"value":4.5}),range(2)))
    assert sorted(r.status_code for r in results) == [201,409]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.post(BASE+"/favorites",headers=headers,json={"movie_id":movies[0]}),range(4)))
    assert all(r.status_code == 204 for r in results)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda value: client.put(BASE+f"/rating/{movies[0]}",headers=headers,json={"value":value}),[2.5,3.5]))
    assert all(r.status_code == 200 for r in results)
    assert len(rows(database,MovieView,user_id)) == len(rows(database,Rating,user_id)) == len(rows(database,UserFavorite,user_id)) == 1
    emitted = events(database,user_id)
    assert [e["aggregate_version"] for e in emitted] == [1,2,3,4,5]
    assert emitted[-1]["payload"]["previous_value"] == emitted[-2]["payload"]["value"]
    assert rows(database,Rating,user_id)[0]["value"] == Decimal(emitted[-1]["payload"]["value"])
