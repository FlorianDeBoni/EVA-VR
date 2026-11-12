from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage
from openai import APIError

from backend.api.main import app
from backend.api.routes import chat as route
from backend.services.chatService import ChatService
from backend.services.errors import PromptNotFoundError
from backend.src.graph.tools.gather_information.schemas import InformationToGather

INFO = InformationToGather(
    user_type="architects",
    number_of_users=5,
    task_description=None,
    goal=None,
    must_have_features=["whiteboard"],
    is_validated=False,
)


class FakeChatService:
    """Records the calls of the route; `session_id` is what ensure_session returns."""

    def __init__(self, session_id=None, error=None):
        self.session_id = session_id or uuid4()
        self.error = error
        self.ensured = None
        self.chatted = None

    def ensure_session(self, session_id):
        self.ensured = session_id
        return self.session_id

    def chat(self, session_id, messages):
        if self.error:
            raise self.error
        self.chatted = (session_id, messages)
        return {
            "messages": [*messages, AIMessage(content="Who will use the room?")],
            "session_id": session_id,
            "information": INFO,
        }


def _post(monkeypatch, service, body):
    monkeypatch.setattr(route, "get_chat_service", lambda: service)
    return TestClient(app).post("/chat", json=body)


def test_chat_runs_the_agent_and_returns_reply_session_and_information(monkeypatch):
    service = FakeChatService()
    known = str(uuid4())

    response = _post(
        monkeypatch,
        service,
        {
            "session_id": known,
            "messages": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
                {"role": "user", "content": "we are architects"},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == str(service.session_id)
    assert body["reply"] == "Who will use the room?"
    assert body["information"] == {
        "user_type": "architects",
        "number_of_users": 5,
        "task_description": None,
        "goal": None,
        "must_have_features": ["whiteboard"],
        "is_validated": False,
    }
    assert str(service.ensured) == known
    session_id, messages = service.chatted
    assert session_id == service.session_id
    assert [type(m) for m in messages] == [HumanMessage, AIMessage, HumanMessage]
    assert [m.content for m in messages] == ["hi", "hello", "we are architects"]


def test_chat_without_session_id_lets_the_service_create_one(monkeypatch):
    service = FakeChatService()

    response = _post(monkeypatch, service, {"messages": [{"role": "user", "content": "hi"}]})

    assert response.status_code == 200
    assert service.ensured is None
    assert response.json()["session_id"] == str(service.session_id)


@pytest.mark.parametrize(
    "body",
    [
        {"messages": []},
        {"messages": [{"role": "user", "content": ""}]},
        {"messages": [{"role": "system", "content": "x"}]},
        {"messages": [{"role": "assistant", "content": "last is not the user"}]},
        {"session_id": "not-a-uuid", "messages": [{"role": "user", "content": "hi"}]},
        {},
    ],
)
def test_chat_rejects_invalid_requests(monkeypatch, body):
    assert _post(monkeypatch, FakeChatService(), body).status_code == 422


def test_chat_maps_a_missing_prompt_to_503(monkeypatch):
    service = FakeChatService(error=PromptNotFoundError("run `task seed:prompts`"))
    response = _post(monkeypatch, service, {"messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 503
    assert "seed:prompts" in response.json()["detail"]


def test_chat_maps_an_openai_error_to_502(monkeypatch):
    error = APIError("upstream down", request=None, body=None)
    response = _post(
        monkeypatch,
        FakeChatService(error=error),
        {"messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 502


# ---- ChatService.ensure_session


class FakeDatabase:
    def __init__(self, existing=()):
        self.existing = set(existing)
        self.created = []

    def session_exists(self, session_id):
        return session_id in self.existing

    def create_session(self, session_id=None):
        new = session_id or uuid4()
        self.created.append(new)
        return new


def test_ensure_session_keeps_an_existing_session():
    known = uuid4()
    db = FakeDatabase(existing=[known])

    assert ChatService(database_service=db).ensure_session(known) == known
    assert db.created == []


def test_ensure_session_creates_an_unknown_session_under_the_same_id():
    unknown = uuid4()
    db = FakeDatabase()

    assert ChatService(database_service=db).ensure_session(unknown) == unknown
    assert db.created == [unknown]


def test_ensure_session_without_id_creates_a_new_one():
    db = FakeDatabase()

    created = ChatService(database_service=db).ensure_session(None)

    assert db.created == [created]
