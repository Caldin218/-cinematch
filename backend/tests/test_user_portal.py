import os
from uuid import uuid4
import pytest
from test_auth import database, client, register, login, auth
from test_catalog import admin, create

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="Requires PostgreSQL/Redis")]

def test_comments_persist_likes_are_idempotent_and_private(client, admin):
    headers, _ = admin
    movie = create(client, headers)
    path = f"/api/v1/movies/{movie['id']}/comments"
    assert client.post(path, json={"body":"Hi"}).status_code == 401
    assert client.post(path, headers=headers, json={"body":" "}).status_code == 422
    assert client.post(path, headers=headers, json={"body":"x"*2001}).status_code == 422
    result = client.post(path, headers=headers, json={"body":"  Beautiful film!  "})
    assert result.status_code == 201, result.text
    comment = result.json()["data"]
    assert comment["body"] == "Beautiful film!" and not comment["liked"]
    like = f"/api/v1/comments/{comment['id']}/like"
    assert client.post(like, headers=headers).status_code == 204
    assert client.post(like, headers=headers).status_code == 204
    own = client.get(path, headers=headers)
    assert own.headers["cache-control"] == "no-store"
    assert own.json()["data"]["items"][0]["liked"] is True
    assert own.json()["data"]["items"][0]["likes"] == 1
    public = client.get(path).json()["data"]
    assert public["items"][0]["liked"] is False and public["items"][0]["likes"] == 1
    email, _ = register(client)
    other = auth(login(client,email)["access_token"])
    assert client.post(like, headers=other).status_code == 204
    assert client.get(path).json()["data"]["items"][0]["likes"] == 2
    assert client.delete(like, headers=headers).status_code == 204
    assert client.delete(like, headers=headers).status_code == 204
    assert client.get(path).json()["data"]["items"][0]["likes"] == 1
    assert client.get(f"/api/v1/movies/{movie['id']}").json()["data"]["comment_count"] == 1
    assert client.get(path,params={"page":2,"page_size":1}).json()["data"]["items"] == []
    assert client.delete(f"/api/v1/admin/movies/{movie['id']}",headers=headers).status_code == 204
    assert client.get(path).status_code == 404
    assert client.post(like,headers=headers).status_code == 404


def test_portal_metadata_search_and_saved_state(client, admin):
    headers, _ = admin
    original=uuid4().hex
    overview=uuid4().hex
    movie=create(client,headers,title="Portal test",original_title=original,synopsis=overview,trailer_youtube_id="dQw4w9WgXcQ")
    assert movie["original_title"] == original and movie["trailer_youtube_id"] == "dQw4w9WgXcQ"
    for q in (original[4:20].upper(),overview[3:20]):
        response=client.get('/api/v1/movies',params={"q":q})
        assert response.status_code == 200, response.text
        assert movie['id'] in [m['id'] for m in response.json()['data']['items']]
    path=f"/api/v1/interactions/movies/{movie['id']}"
    assert client.get(path).status_code == 401
    assert client.get(path,headers=headers).json()['data']=={"rating":None,"watchlist":False,"favorite":False,"watched":False}
    for collection in ('watchlist','favorites'):
        assert client.post(f'/api/v1/interactions/{collection}',headers=headers,json={"movie_id":movie['id']}).status_code == 204
    assert client.post('/api/v1/interactions/rating',headers=headers,json={"movie_id":movie['id'],"value":4.5}).status_code == 201
    assert client.post('/api/v1/interactions/view',headers=headers,json={"movie_id":movie['id'],"request_id":str(uuid4())}).status_code == 200
    assert client.get(path,headers=headers).json()['data']=={"rating":4.5,"watchlist":True,"favorite":True,"watched":True}
    assert client.get('/api/v1/movies',headers=headers,params={"sort":"match","q":"Portal test"}).status_code == 200
    assert client.post('/api/v1/admin/movies',headers=headers,json={"title":"Bad","trailer_youtube_id":"javascript:bad"}).status_code == 422
