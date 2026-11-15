from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.health import get_health_service
from app.core.config import Settings
from app.core.health import HealthService
from app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as client:
        yield client


def test_liveness_does_not_require_dependencies(client):
    for path in ("/health", "/health/live"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "checks": {}}


@pytest.mark.parametrize("failed", [None, "postgresql", "redis", "both"])
def test_readiness_reports_dependency_failure(client, monkeypatch, failed):
    database = Mock(side_effect=RuntimeError("secret") if failed in ("postgresql", "both") else None)
    redis = Mock(side_effect=RuntimeError("secret") if failed in ("redis", "both") else None)
    monkeypatch.setattr("app.core.health.check_database", database)
    monkeypatch.setattr("app.core.health.check_redis", redis)
    service = HealthService(Mock(), Mock())
    client.app.dependency_overrides[get_health_service] = lambda: service
    response = client.get("/health/ready")
    assert response.status_code == (503 if failed else 200)
    assert response.json()["checks"] == {
        "postgresql": "down" if failed in ("postgresql", "both") else "up",
        "redis": "down" if failed in ("redis", "both") else "up",
    }
    assert "secret" not in response.text
    database.assert_called_once()
    redis.assert_called_once()


def test_lifespan_closes_resources(monkeypatch):
    engine, redis = Mock(), Mock()
    monkeypatch.setattr("app.main.create_database_engine", lambda _: engine)
    monkeypatch.setattr("app.main.create_redis_client", lambda _: redis)
    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200
    engine.dispose.assert_called_once()
    redis.close.assert_called_once()


def test_database_url_escapes_password():
    settings = Settings(postgres_user="user", postgres_password="p@ss:/?#%",
                        postgres_db="db", redis_url="redis://localhost:6379/0")
    assert settings.database_url.password == "p@ss:/?#%"
    assert "p@ss" not in repr(settings)
