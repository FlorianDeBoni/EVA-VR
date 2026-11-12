from types import SimpleNamespace

import pytest
from langfuse.api import NotFoundError

from backend.infra import langfuseClient as client_module
from backend.infra.langfuseClient import LangfuseClient
from backend.services import promptService as service_module
from backend.services.errors import PromptNotFoundError
from backend.services.promptService import PromptService


class FakeLangfuse:
    """Records get_prompt / create_prompt calls; serves `remote` prompts by name."""

    def __init__(self, remote=None):
        self.remote = remote or {}
        self.get_calls = []
        self.created = []
        self.flushed = False

    def get_prompt(self, name, **kwargs):
        self.get_calls.append((name, kwargs))
        if name not in self.remote:
            raise NotFoundError(body={})
        text = self.remote[name]
        return SimpleNamespace(
            prompt=text,
            compile=lambda **v: text.replace("{{x}}", v.get("x", "")),
        )

    def create_prompt(self, **kwargs):
        self.created.append(kwargs)

    def flush(self):
        self.flushed = True


@pytest.fixture
def prompts_dir(tmp_path):
    (tmp_path / "hello.md").write_text("Hello {{x}}", encoding="utf-8")
    return tmp_path


def _service(client):
    return PromptService(client=client, label="production")


def test_get_reads_the_labelled_prompt_from_langfuse_and_compiles_it():
    client = FakeLangfuse(remote={"hello": "Remote {{x}}"})

    assert _service(client).get("hello", x="world") == "Remote world"
    assert client.get_calls == [("hello", {"label": "production", "type": "text"})]


def test_get_unknown_prompt_points_to_the_seed_task():
    with pytest.raises(PromptNotFoundError, match="seed:prompts"):
        _service(FakeLangfuse()).get("nope")


def test_seed_creates_updates_and_skips_unchanged(prompts_dir):
    (prompts_dir / "same.md").write_text("same", encoding="utf-8")
    (prompts_dir / "old.md").write_text("new text", encoding="utf-8")
    (prompts_dir / "ignored.txt").write_text("not a prompt", encoding="utf-8")
    client = FakeLangfuse(remote={"same": "same", "old": "old text"})

    result = _service(client).seed(prompts_dir)

    assert result == {"hello": "created", "old": "updated", "same": "unchanged"}
    assert {c["name"] for c in client.created} == {"hello", "old"}
    assert all(c["labels"] == ["production"] and c["type"] == "text" for c in client.created)
    assert next(c for c in client.created if c["name"] == "hello")["prompt"] == "Hello {{x}}"
    assert client.flushed


def test_client_is_built_lazily_from_env_and_cached(monkeypatch):
    built = []
    monkeypatch.setattr(client_module, "Langfuse", lambda **kw: built.append(kw) or object())
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setenv("LANGFUSE_HOST", "http://lf")

    client = LangfuseClient.from_env()
    assert not built
    assert client.get_client() is client.get_client()
    assert built == [{"public_key": "pk", "secret_key": "sk", "host": "http://lf"}]


def test_label_comes_from_env(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PROMPT_LABEL", "staging")
    assert PromptService(client=FakeLangfuse()).label == "staging"


def test_shared_service_is_cached():
    service_module.get_prompt_service.cache_clear()
    assert service_module.get_prompt_service() is service_module.get_prompt_service()
