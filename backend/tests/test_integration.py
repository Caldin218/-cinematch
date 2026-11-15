import os

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="Set RUN_INTEGRATION=1 with real services")
def test_real_postgres_and_redis_readiness():
    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200
        response = client.get("/health/ready")
        assert response.status_code == 200, response.text
        assert response.json() == {
            "status": "ready", "checks": {"postgresql": "up", "redis": "up"},
        }
