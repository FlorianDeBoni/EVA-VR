import pytest
from settings.envManager import EnvKeyName, EnvManager


def test_returns_value_when_set(monkeypatch):
    monkeypatch.setenv("GEMINI_KEY", "abc123")
    assert EnvManager.get_env_variable(EnvKeyName.KEY_GEMINI_KEY) == "abc123"


def test_returns_empty_string_when_set_empty(monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "")
    assert EnvManager.get_env_variable(EnvKeyName.KEY_SERPAPI_KEY) == ""


def test_raises_key_error_when_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_KEY", raising=False)
    with pytest.raises(KeyError, match="GEMINI_KEY"):
        EnvManager.get_env_variable(EnvKeyName.KEY_GEMINI_KEY)


@pytest.mark.parametrize(
    ("member", "name"),
    [
        (EnvKeyName.KEY_GEMINI_KEY, "GEMINI_KEY"),
        (EnvKeyName.KEY_SERPAPI_KEY, "SERPAPI_KEY"),
    ],
)
def test_env_key_values(member, name):
    assert member.value == name
