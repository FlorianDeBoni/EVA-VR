import pytest
from fastapi.testclient import TestClient

from backend.api.main import app


@pytest.mark.parametrize("path", ["/health/live", "/health/ready"])
def test_health_endpoints_return_ok(path: str) -> None:
    response = TestClient(app).get(path)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
