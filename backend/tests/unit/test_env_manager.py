import pytest

from backend.src.settings.envManager import EnvKeyName, EnvManager


def test_returns_value_when_set(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "abc123")
    assert EnvManager.get_env_variable(EnvKeyName.KEY_OPENAI_API_KEY) == "abc123"


def test_returns_empty_string_when_set_empty(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    assert EnvManager.get_env_variable(EnvKeyName.KEY_OPENAI_API_KEY) == ""


def test_raises_key_error_when_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(KeyError, match="OPENAI_API_KEY"):
        EnvManager.get_env_variable(EnvKeyName.KEY_OPENAI_API_KEY)


def test_returns_default_when_missing(monkeypatch):
    monkeypatch.delenv("GPT_COMPLETION_MODEL", raising=False)
    assert EnvManager.get_env_variable(EnvKeyName.KEY_GPT_COMPLETION_MODEL, "m1") == "m1"


def test_set_value_wins_over_default(monkeypatch):
    monkeypatch.setenv("GPT_COMPLETION_MODEL", "m2")
    assert EnvManager.get_env_variable(EnvKeyName.KEY_GPT_COMPLETION_MODEL, "m1") == "m2"


@pytest.mark.parametrize(
    ("member", "name"),
    [
        (EnvKeyName.KEY_API_PORT, "API_PORT"),
        (EnvKeyName.KEY_OPENAI_API_KEY, "OPENAI_API_KEY"),
        (EnvKeyName.KEY_OPENAI_IMAGE_MODEL, "OPENAI_IMAGE_MODEL"),
        (EnvKeyName.KEY_GPT_COMPLETION_MODEL, "GPT_COMPLETION_MODEL"),
    ],
)
def test_env_key_values(member, name):
    assert member.value == name
