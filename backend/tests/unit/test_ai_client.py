import pytest
from openai import OpenAI

from backend.infra.AIClient import AIClient


def test_builds_openai_client():
    client = AIClient("sk-test").get_client()
    assert type(client) is OpenAI
    assert client.api_key == "sk-test"


def test_client_is_cached():
    ai = AIClient("sk-test")
    assert ai.get_client() is ai.get_client()


def test_from_env_builds_openai_client(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    ai = AIClient.from_env()
    assert type(ai.get_client()) is OpenAI


def test_missing_env_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(KeyError):
        AIClient.from_env()
