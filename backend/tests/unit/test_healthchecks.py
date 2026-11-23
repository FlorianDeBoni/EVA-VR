from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.routes import healthchecks


class FakeClient:
    """Stands in for DatabaseClient: connection() works or raises."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.queries: list[str] = []

    @contextmanager
    def connection(self):
        if self.error:
            raise self.error
        yield SimpleNamespace(execute=self.queries.append)


def _use_client(monkeypatch: pytest.MonkeyPatch, client: FakeClient) -> None:
    monkeypatch.setattr(
        healthchecks, "get_database_service", lambda: SimpleNamespace(client=client)
    )


def test_live_returns_ok() -> None:
    response = TestClient(app).get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_ok_when_database_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient()
    _use_client(monkeypatch, client)

    response = TestClient(app).get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert client.queries == ["SELECT 1"]


def test_ready_returns_503_when_database_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_client(monkeypatch, FakeClient(error=ConnectionError("refused")))

    response = TestClient(app).get("/health/ready")

    assert response.status_code == 503
