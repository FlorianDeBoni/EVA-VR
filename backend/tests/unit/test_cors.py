from fastapi.testclient import TestClient

from backend.api.main import create_app


def _client(monkeypatch, origins):
    monkeypatch.setenv("CORS_ORIGINS", origins)
    return TestClient(create_app())


def test_allowed_origin_gets_cors_headers(monkeypatch):
    client = _client(monkeypatch, "http://localhost:5173, http://other:3000")

    response = client.get("/health/live", headers={"Origin": "http://other:3000"})

    assert response.headers["access-control-allow-origin"] == "http://other:3000"


def test_preflight_for_the_chat_post_is_accepted(monkeypatch):
    client = _client(monkeypatch, "http://localhost:5173")

    response = client.options(
        "/chat",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_unknown_origin_gets_no_cors_headers(monkeypatch):
    client = _client(monkeypatch, "http://localhost:5173")

    response = client.get("/health/live", headers={"Origin": "http://evil.example"})

    assert "access-control-allow-origin" not in response.headers
