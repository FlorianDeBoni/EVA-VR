from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from openai import APIError

from backend.api.main import app
from backend.api.routes import speech
from backend.services import speechToTextService as module
from backend.services.speechToTextService import SpeechToTextError, SpeechToTextService


@pytest.fixture(autouse=True)
def stt_env(monkeypatch):
    monkeypatch.setenv("OPENAI_STT_MODEL", "stt-model")
    monkeypatch.setenv("STT_MAX_AUDIO_BYTES", "100")
    monkeypatch.setenv("STT_LANGUAGE", "en")


class FakeOpenAI:
    def __init__(self, text="bonjour"):
        self.calls = []
        self._text = text
        self.audio = SimpleNamespace(transcriptions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text=self._text)


def test_transcribe_sends_file_model_and_options():
    client = FakeOpenAI()
    text = SpeechToTextService(client=client).transcribe(
        b"abc", "voice.webm", "audio/webm", language="fr", prompt="EVA"
    )

    assert text == "bonjour"
    assert client.calls == [
        {
            "model": "stt-model",
            "file": ("voice.webm", b"abc", "audio/webm"),
            "language": "fr",
            "prompt": "EVA",
        }
    ]


def test_language_defaults_to_the_configured_one_and_other_options_are_omitted():
    client = FakeOpenAI()
    SpeechToTextService(client=client).transcribe(b"abc", "v.wav")
    assert client.calls == [{"model": "stt-model", "file": ("v.wav", b"abc"), "language": "en"}]


def test_language_comes_from_env_and_can_be_overridden(monkeypatch):
    monkeypatch.setenv("STT_LANGUAGE", "de")
    client = FakeOpenAI()
    service = SpeechToTextService(client=client)

    service.transcribe(b"abc", "v.wav")
    service.transcribe(b"abc", "v.wav", language="fr")

    assert [c["language"] for c in client.calls] == ["de", "fr"]


def test_empty_and_oversized_audio_are_rejected():
    service = SpeechToTextService(client=FakeOpenAI())
    with pytest.raises(SpeechToTextError):
        service.transcribe(b"", "v.wav")
    with pytest.raises(SpeechToTextError):
        service.transcribe(b"x" * 101, "v.wav")


def test_client_is_built_lazily_from_env_key_and_cached(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    service = SpeechToTextService()
    assert service.client.api_key == "sk-env"
    assert service.client is service.client


def test_shared_service_is_cached():
    module.get_speech_to_text_service.cache_clear()
    assert module.get_speech_to_text_service() is module.get_speech_to_text_service()


class FakeService:
    def __init__(self, error=None):
        self.seen = None
        self._error = error

    def transcribe(self, audio, filename, content_type=None, language=None, prompt=None):
        self.seen = (audio, filename, content_type, language, prompt)
        if self._error:
            raise self._error
        return "salut"


def _post(monkeypatch, service, **data):
    monkeypatch.setattr(speech, "get_speech_to_text_service", lambda: service)
    return TestClient(app).post(
        "/speech/transcribe",
        files={"file": ("voice.webm", b"abc", "audio/webm")},
        data=data,
    )


def test_endpoint_proxies_upload_to_service(monkeypatch):
    service = FakeService()
    response = _post(monkeypatch, service, language="fr")

    assert response.status_code == 200
    assert response.json() == {"text": "salut"}
    assert service.seen == (b"abc", "voice.webm", "audio/webm", "fr", None)


def test_endpoint_maps_invalid_audio_to_422(monkeypatch):
    response = _post(monkeypatch, FakeService(SpeechToTextError("audio is empty")))
    assert response.status_code == 422


def test_endpoint_maps_upstream_error_to_502(monkeypatch):
    error = APIError("upstream down", request=SimpleNamespace(), body=None)
    response = _post(monkeypatch, FakeService(error))
    assert response.status_code == 502


def test_endpoint_requires_a_file():
    assert TestClient(app).post("/speech/transcribe").status_code == 422
