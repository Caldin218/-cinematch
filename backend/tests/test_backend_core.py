import asyncio
from unittest.mock import AsyncMock
from uuid import UUID, uuid4
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from app.main import create_app
from app.core.api import ApiResponse, Pagination
from app.core.errors import ApplicationError
from app.core.runtime import get_db
from app.core.correlation import request_id


def test_errors_versioning_and_correlation():
    app = create_app()
    @app.get("/test/error")
    def error():
        raise ApplicationError("conflict", "Safe message", 409)
    @app.get("/test/crash")
    def crash():
        raise RuntimeError("secret password")
    @app.get("/test/value")
    def value(number: int):
        return ApiResponse(data=number)
    with TestClient(app) as client:
        identifier = str(uuid4())
        response = client.get("/test/error", headers={"X-Request-ID": identifier})
        assert response.status_code == 409
        assert response.json()["request_id"] == identifier
        assert response.headers["x-request-id"] == identifier
        response = client.get("/test/crash")
        assert response.status_code == 500
        assert "secret" not in response.text
        assert UUID(response.headers["x-request-id"])
        assert client.get("/test/value?number=bad").status_code == 422
        assert client.get("/test/value?number=3").json() == {"data":3}
        assert client.get("/absent").json()["code"] == "http_404"
        assert client.get("/api/v1/health").json()["status"] == "ok"
        assert request_id.get() is None


def test_async_resources_close_and_request_sessions_rollback(monkeypatch):
    engine, redis, session = AsyncMock(), AsyncMock(), AsyncMock()
    session.__aenter__.return_value = session
    monkeypatch.setattr("app.main.create_async_resources", lambda _: (engine, redis, lambda: session))
    app = create_app()
    @app.get("/test/session")
    async def use_session(db=Depends(get_db)):
        return {"ok": True}
    with TestClient(app) as client:
        assert client.get("/test/session").status_code == 200
    session.rollback.assert_awaited_once()
    session.__aexit__.assert_awaited_once()
    redis.aclose.assert_awaited_once()
    engine.dispose.assert_awaited_once()


def test_pagination_bounds():
    assert Pagination(page=3, page_size=10).offset == 20
    for values in ({"page":0}, {"page_size":101}):
        with pytest.raises(ValueError):
            Pagination(**values)
