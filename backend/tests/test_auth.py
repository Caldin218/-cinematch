import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, update
from alembic import command
from app.core.config import get_settings
from app.main import create_app
from app.models import User, RefreshToken
from app.modules.auth.dependencies import require_admin
from app.modules.auth.limiter import AuthLimiter, get_limiter
from app.modules.auth.security import token_hash, hasher
from test_database_schema import temporary_database, alembic_config

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="Requires PostgreSQL/Redis")]
PASSWORD = "correct horse battery staple"

@pytest.fixture(scope="module")
def database():
    with temporary_database() as engine:
        with engine.connect() as c:
            command.upgrade(alembic_config(c), "head")
        yield engine

@pytest.fixture
def client(database):
    config = get_settings().model_copy(update={"postgres_db": database.url.database,
        "jwt_secret": __import__("pydantic").SecretStr(secrets.token_urlsafe(48))})
    app = create_app(config)
    app.user_middleware = [m for m in app.user_middleware if m.cls.__name__ != "CorrelationMiddleware"]
    # A unique test client IP preserves real limiter behavior without touching others' keys.
    ip = "audit-" + uuid4().hex
    app.dependency_overrides[get_limiter] = lambda: AuthLimiter(app.state.async_redis, ip)
    @app.get("/test/admin")
    async def admin(user=Depends(require_admin)):
        return {"role":user.role}
    with TestClient(app) as client:
        yield client


def register(client):
    email = uuid4().hex + "@example.com"
    result = client.post("/api/v1/auth/register", json={"email":email, "password":PASSWORD, "display_name":"Test User"})
    assert result.status_code == 201, result.text
    return email, result.json()["data"]


def login(client, email):
    result = client.post("/api/v1/auth/login", json={"email":email,"password":PASSWORD})
    assert result.status_code == 200, result.text
    assert result.headers["cache-control"] == "no-store"
    assert not result.cookies
    return result.json()["data"]


def auth(token):
    return {"Authorization":"Bearer " + token}


def test_registration_duplicate_validation_and_hash(client, database):
    email, user = register(client)
    assert user["role"] == "USER" and "password_hash" not in user
    data = {"email":email,"password":PASSWORD,"display_name":"Duplicate"}
    assert client.post("/api/v1/auth/register",json=data).status_code == 409
    assert client.post("/api/v1/auth/register",json=data | {"password":"short"}).status_code == 422
    assert client.post("/api/v1/auth/register",json=data | {"role":"ADMIN"}).status_code == 422
    with database.connect() as c:
        encoded = c.scalar(select(User.password_hash).where(User.email == email))
        assert encoded.startswith("$argon2id$") and hasher.verify(encoded, PASSWORD)


def test_login_me_logout_and_admin_denial(client):
    email, user = register(client)
    tokens = login(client, email.upper())
    headers = auth(tokens["access_token"])
    response = client.get("/api/v1/users/me",headers=headers)
    assert response.status_code == 200 and response.json()["data"] == user
    assert client.get("/api/v1/users/me").status_code == 401
    assert client.get("/test/admin",headers=headers).status_code == 403
    assert client.post("/api/v1/auth/logout",json={"refresh_token":tokens["refresh_token"]}).status_code == 204
    assert client.get("/api/v1/users/me",headers=headers).status_code == 401
    assert client.post("/api/v1/auth/refresh",json={"refresh_token":tokens["refresh_token"]}).status_code == 401
    assert client.post("/api/v1/auth/logout",json={"refresh_token":tokens["refresh_token"]}).status_code == 204


def test_invalid_credentials_and_login_limit(client):
    email, _ = register(client)
    for _ in range(5):
        response = client.post("/api/v1/auth/login",json={"email":email,"password":"wrong"})
        assert response.status_code == 401
        assert response.json()["message"] == "Invalid email or password"
    assert client.post("/api/v1/auth/login",json={"email":email,"password":PASSWORD}).status_code == 429


def test_expired_tampered_and_wrong_audience_access(client):
    email, _ = register(client)
    token = login(client,email)["access_token"]
    config = client.app.state.settings
    key = config.jwt_secret.get_secret_value()
    claims = jwt.decode(token,key,algorithms=["HS256"],audience=config.jwt_audience)
    for changes in ({"exp":datetime.now(timezone.utc)-timedelta(seconds=1)}, {"aud":"other"}, {"iss":"other"}):
        invalid = jwt.encode(claims | changes,key,algorithm="HS256")
        assert client.get("/api/v1/users/me",headers=auth(invalid)).status_code == 401
    assert client.get("/api/v1/users/me",headers=auth(token+"bad")).status_code == 401


def test_rotation_reuse_revokes_family_and_hashes_only(client,database):
    email, _ = register(client)
    old = login(client,email)
    response = client.post("/api/v1/auth/refresh",json={"refresh_token":old["refresh_token"]})
    assert response.status_code == 200, response.text
    new = response.json()["data"]
    assert new["refresh_token"] != old["refresh_token"]
    assert client.get("/api/v1/users/me",headers=auth(new["access_token"])).status_code == 200
    with database.connect() as c:
        row = c.execute(select(RefreshToken.token_hash, RefreshToken.consumed_at).where(RefreshToken.token_hash == token_hash(old["refresh_token"]))).one()
        assert row.consumed_at is not None and row.token_hash != old["refresh_token"]
    reused = client.post("/api/v1/auth/refresh",json={"refresh_token":old["refresh_token"]})
    assert reused.status_code == 401 and reused.json()["code"] == "refresh_reuse"
    assert client.get("/api/v1/users/me",headers=auth(new["access_token"])).status_code == 401
    assert client.post("/api/v1/auth/refresh",json={"refresh_token":new["refresh_token"]}).status_code == 401


def test_admin_role_and_suspension_checked_live(client,database):
    email, user = register(client)
    tokens = login(client,email)
    from uuid import UUID
    with database.begin() as c:
        c.execute(update(User).where(User.id==UUID(user["id"])).values(role="ADMIN"))
    assert client.get("/test/admin",headers=auth(tokens["access_token"])).status_code == 200
    with database.begin() as c:
        c.execute(update(User).where(User.id==UUID(user["id"])).values(status="suspended"))
    assert client.get("/api/v1/users/me",headers=auth(tokens["access_token"])).status_code == 401
    assert client.post("/api/v1/auth/login",json={"email":email,"password":PASSWORD}).status_code == 401


def test_concurrent_rotation_only_one_success_then_family_revoked(client):
    email, _ = register(client)
    tokens = login(client,email)
    def rotate():
        return client.post("/api/v1/auth/refresh",json={"refresh_token":tokens["refresh_token"]})
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: rotate(), range(2)))
    assert sorted(r.status_code for r in results) == [200,401]
    winning = next(r.json()["data"] for r in results if r.status_code==200)
    assert client.get("/api/v1/users/me",headers=auth(winning["access_token"])).status_code == 401


def test_limiter_dependency_outage_fails_closed(client):
    from redis.exceptions import ConnectionError
    from unittest.mock import AsyncMock
    unavailable = AsyncMock()
    unavailable.eval.side_effect = ConnectionError("private credentials")
    client.app.dependency_overrides[get_limiter] = lambda: AuthLimiter(unavailable,"test")
    response = client.post("/api/v1/auth/login",json={"email":"unknown@example.com","password":PASSWORD})
    assert response.status_code == 503 and "private" not in response.text
