from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.routes import detailed_design as route
from backend.services.errors import (
    DetailedDesignNotFoundError,
    DetailedImageOutdatedError,
    SessionNotFoundError,
)
from backend.src.graph.tools.detailed_design.schemas import Detail, DetailCategory, DetailedDesign

TABLE = Detail("Round table", DetailCategory.FURNITURE, "oak, 6 seats", "Lab", 2)
PALETTE = Detail("Palette", DetailCategory.COLOR, "white and sage")
READY = DetailedDesign([TABLE, PALETTE], is_validated=False, latest_image_version=6)


class FakeService:
    """Stands in for DetailedDesignService: one design, records the validation."""

    def __init__(self, design=READY, error=None, get_error=None):
        self.design = design
        self.error = error
        self.get_error = get_error
        self.validated = []

    def get_detailed_design(self, session_id):
        if self.get_error:
            raise self.get_error
        return self.design

    def validate(self, session_id, version):
        if self.error:
            raise self.error
        self.validated.append((session_id, version))


def post(monkeypatch, service, body=None, session_id=None):
    monkeypatch.setattr(route, "get_detailed_design_service", lambda: service)
    session_id = session_id or uuid4()
    response = TestClient(app).post(f"/detailed-design/{session_id}/validate", json=body)
    return response, session_id


def test_validate_keeps_the_latest_picture_and_returns_the_validated_design(monkeypatch):
    service = FakeService()

    response, session_id = post(monkeypatch, service)

    assert response.status_code == 200
    assert service.validated == [(session_id, 6)]
    body = response.json()
    assert body["is_validated"] is True
    assert body["latest_image_version"] == 6
    assert [d["name"] for d in body["details"]] == ["Round table", "Palette"]
    assert body["details"][0] == {
        "name": "Round table",
        "category": "furniture",
        "description": "oak, 6 seats",
        "space": "Lab",
        "quantity": 2,
    }


def test_validate_can_keep_an_earlier_picture(monkeypatch):
    service = FakeService()

    response, session_id = post(monkeypatch, service, {"version": 4})

    assert response.status_code == 200
    assert service.validated == [(session_id, 4)]


@pytest.mark.parametrize(
    ("design", "expected"),
    [
        (DetailedDesign([], False, 6), "no piece of furniture"),
        (DetailedDesign([PALETTE], False, 6), "no piece of furniture"),
        (DetailedDesign([TABLE], False, None), "no picture"),
    ],
)
def test_validate_refuses_an_incomplete_design_like_the_assistant_does(
    monkeypatch, design, expected
):
    service = FakeService(design)

    response, _ = post(monkeypatch, service)

    assert response.status_code == 409
    assert expected in response.json()["detail"]
    assert service.validated == []


def test_validate_refuses_a_picture_made_before_the_last_change(monkeypatch):
    service = FakeService(error=DetailedImageOutdatedError("old"))

    response, _ = post(monkeypatch, service)

    assert response.status_code == 409
    assert "changed after this picture" in response.json()["detail"]


def test_validate_answers_404_for_an_unknown_session_or_picture(monkeypatch):
    unknown, _ = post(monkeypatch, FakeService(get_error=SessionNotFoundError("no session")))
    missing, _ = post(
        monkeypatch, FakeService(error=DetailedDesignNotFoundError("none")), {"version": 9}
    )

    assert unknown.status_code == 404 and "no session" in unknown.json()["detail"]
    assert missing.status_code == 404 and "picture version 9" in missing.json()["detail"]


def test_validate_rejects_a_bad_version(monkeypatch):
    response, _ = post(monkeypatch, FakeService(), {"version": 0})

    assert response.status_code == 422
