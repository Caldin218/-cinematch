import os
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from redis.exceptions import ConnectionError
from sqlalchemy import insert, select, update, event
from app.models import User, Movie, Rating, MovieView, OutboxEvent
from app.core.runtime import get_redis
from test_auth import database, client, register, login, auth

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="Requires PostgreSQL/Redis")]

@pytest.fixture
def admin(client, database):
    email, user = register(client)
    with database.begin() as c:
        c.execute(update(User).where(User.id == UUID(user["id"])).values(role="ADMIN"))
    return auth(login(client, email)["access_token"]), UUID(user["id"])

def create(client, headers, **fields):
    response = client.post("/api/v1/admin/movies", headers=headers, json={"title": uuid4().hex, **fields})
    assert response.status_code == 201, response.text
    return response.json()["data"]

def genre(client, headers):
    result = client.post("/api/v1/admin/genres", headers=headers, json={"name": uuid4().hex})
    assert result.status_code == 201, result.text
    return result.json()["data"]

def test_catalog_filters_sorting_and_pagination(client, admin, database):
    headers, user_id = admin
    g = genre(client, headers)
    prefix = uuid4().hex
    a = create(client, headers, title=prefix+" A", release_year=2000, genre_ids=[g["id"]])
    b = create(client, headers, title=prefix+" B", release_year=2020, genre_ids=[g["id"]])
    c = create(client, headers, title=prefix+" C", release_year=None)
    with database.begin() as conn:
        conn.execute(insert(Rating), [{"user_id": user_id, "movie_id": a["id"], "value": 5},
                                      {"user_id": user_id, "movie_id": b["id"], "value": 2}])
        conn.execute(insert(MovieView), [{"user_id": user_id, "movie_id": b["id"], "request_id": uuid4()} for _ in range(2)])
    def listing(**params):
        r = client.get("/api/v1/movies", params={"q": prefix, **params})
        assert r.status_code == 200, r.text
        return r.json()["data"]
    assert [x["id"] for x in listing(sort="rating")["items"]] == [a["id"], b["id"], c["id"]]
    popular = listing(sort="popularity")["items"]
    assert popular[0]["id"] == b["id"] and popular[0]["popularity"] == 2
    assert popular[0]["rating_count"] == 1 and popular[0]["average_rating"] == 2
    assert [x["id"] for x in listing(sort="release_year")["items"]] == [b["id"], a["id"], c["id"]]
    assert listing(genre_id=g["id"])["total"] == 2
    assert listing(release_year=2000)["items"][0]["id"] == a["id"]
    assert listing(min_rating=4)["total"] == 1
    assert listing(max_rating=3)["total"] == 1
    assert listing(min_rating=3, max_rating=4)["total"] == 0
    page = listing(page_size=1, page=2, sort="rating")
    assert page["total"] == 3 and page["items"][0]["id"] == b["id"]
    assert listing(page=99)["items"] == []
    assert client.get("/api/v1/movies/search", params={"q": prefix.upper()}).json()["data"]["total"] == 3
    special = create(client, headers, title=prefix+"%_literal")
    assert listing(q=prefix+"%_")["items"][0]["id"] == special["id"]
    statements = []
    engine = client.app.state.async_sessions.kw["bind"].sync_engine
    def record(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(engine, "before_cursor_execute", record)
    try:
        listing(page_size=100)
        assert len(statements) == 3
    finally:
        event.remove(engine, "before_cursor_execute", record)


def test_admin_crud_genre_management_and_outbox(client, admin, database):
    headers, _ = admin
    g = genre(client, headers)
    movie = create(client, headers, genre_ids=[g["id"]], synopsis="Plot")
    assert movie["genres"] == [g] and movie["version"] == 1
    patched = client.patch(f"/api/v1/admin/movies/{movie['id']}", headers=headers,
        json={"title": "Changed", "synopsis": None, "genre_ids": []})
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["version"] == 2
    assert patched.json()["data"]["genres"] == []
    assert client.get(f"/api/v1/movies/{movie['id']}").json()["data"]["synopsis"] is None
    assert client.delete(f"/api/v1/admin/movies/{movie['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/movies/{movie['id']}").status_code == 404
    assert client.patch(f"/api/v1/admin/movies/{movie['id']}", headers=headers, json={"title":"Again"}).status_code == 404
    with database.connect() as conn:
        events = conn.execute(select(OutboxEvent.event_type, OutboxEvent.aggregate_version).where(
            OutboxEvent.aggregate_type == "movie", OutboxEvent.aggregate_id == str(movie["id"])).order_by(OutboxEvent.aggregate_version)).all()
        assert events == [("movie.created",1),("movie.updated",2),("movie.deleted",3)]
        assert conn.scalar(select(Movie.is_active).where(Movie.id == movie["id"])) is False
    assert client.get("/api/v1/genres").status_code == 200
    rename = client.patch(f"/api/v1/admin/genres/{g['id']}", headers=headers, json={"name":g["name"]+" renamed"})
    assert rename.status_code == 200
    assert rename.json()["data"] in client.get("/api/v1/genres").json()["data"]
    assert client.delete(f"/api/v1/admin/genres/{g['id']}", headers=headers).status_code == 204
    assert client.delete(f"/api/v1/admin/genres/{g['id']}", headers=headers).status_code == 404


def test_validation_and_conflicts(client, admin, database):
    headers, _ = admin
    for params in ({"page":0}, {"page":1000001}, {"page_size":101}, {"sort":"bad"}, {"release_year":1800},
                   {"min_rating":6}, {"min_rating":4,"max_rating":2}, {"q":" "}, {"genre_id":-1}):
        assert client.get("/api/v1/movies", params=params).status_code == 422
    for value in ("abc", "0", "-1", "9223372036854775808"):
        assert client.get("/api/v1/movies/"+value).status_code == 422
    assert client.get("/api/v1/movies/9223372036854775807").status_code == 404
    for data in ({"title":" "}, {"title":"Valid","release_year":1800}, {"title":"Valid","genre_ids":[1,1]},
                 {"title":"Valid","poster_url":"javascript:alert(1)"}, {"title":"Valid","unknown":1}):
        assert client.post("/api/v1/admin/movies", headers=headers, json=data).status_code == 422
    assert client.post("/api/v1/admin/movies", headers=headers, json={"title":"Invalid genre", "genre_ids":[9223372036854775807]}).status_code == 422
    g = genre(client, headers)
    assert client.post("/api/v1/admin/genres", headers=headers, json={"name":g["name"].upper()}).status_code == 409
    m = create(client, headers, genre_ids=[g["id"]])
    assert client.delete(f"/api/v1/admin/genres/{g['id']}", headers=headers).status_code == 409
    for patch in ({}, {"title":None}, {"genre_ids":None}):
        assert client.patch(f"/api/v1/admin/movies/{m['id']}", headers=headers, json=patch).status_code == 422


def test_authorization(client, admin):
    admin_headers, _ = admin
    email, _ = register(client)
    user_headers = auth(login(client,email)["access_token"])
    m = create(client, admin_headers)
    g = genre(client, admin_headers)
    for headers, status in (({},401), (user_headers,403)):
        for method, path, data in (("post","movies",{"title":"No"}), ("patch",f"movies/{m['id']}",{"title":"No"}),
            ("delete",f"movies/{m['id']}",None), ("post","genres",{"name":"No"}),
            ("patch",f"genres/{g['id']}",{"name":"No"}), ("delete",f"genres/{g['id']}",None)):
            assert client.request(method,"/api/v1/admin/"+path,headers=headers,json=data).status_code == status


def test_genre_cache_hit_corruption_and_outage(client, admin):
    headers, _ = admin
    g = genre(client, headers)
    redis = AsyncMock()
    client.app.dependency_overrides[get_redis] = lambda: redis
    try:
        redis.get.return_value = '[{"id":123,"name":"Cached"}]'
        assert client.get("/api/v1/genres").json()["data"] == [{"id":123,"name":"Cached"}]
        redis.get.return_value = "bad JSON"
        assert g in client.get("/api/v1/genres").json()["data"]
        redis.get.side_effect = ConnectionError("offline")
        redis.set.side_effect = ConnectionError("offline")
        redis.delete.side_effect = ConnectionError("offline")
        assert g in client.get("/api/v1/genres").json()["data"]
        assert client.patch(f"/api/v1/admin/genres/{g['id']}", headers=headers, json={"name":uuid4().hex}).status_code == 200
    finally:
        client.app.dependency_overrides.pop(get_redis)
