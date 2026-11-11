import base64
from types import SimpleNamespace

import pytest

from backend.src.graph.tools.generate_image.generate_image import ImageGeneratorService
from backend.src.graph.tools.generate_image.schemas import GeneratedImage, ImageGenerationError

PNG = b"\x89PNG fake"
PNG_B64 = base64.b64encode(PNG).decode()


@pytest.fixture(autouse=True)
def max_past(monkeypatch):
    monkeypatch.setenv("MAX_PAST_IMAGES", "3")


def _gen(client, **kwargs):
    return ImageGeneratorService(client=client, model=kwargs.pop("model", "m"), **kwargs)


def _response(b64=PNG_B64):
    return SimpleNamespace(data=[SimpleNamespace(b64_json=b64)] if b64 else [])


class FakeOpenAI:
    """Records each images call and answers with the given response."""

    def __init__(self, response=None):
        self._response = response or _response()
        self.generate_calls = []
        self.edit_calls = []
        self.images = SimpleNamespace(generate=self._generate, edit=self._edit)

    def _generate(self, **kwargs):
        self.generate_calls.append(kwargs)
        return self._response

    def _edit(self, **kwargs):
        self.edit_calls.append(kwargs)
        return self._response


def test_no_past_images_uses_generate():
    client = FakeOpenAI()

    result = _gen(client).generate("a pavilion")

    assert result == GeneratedImage(PNG, "image/png")
    assert client.generate_calls == [{"model": "m", "prompt": "a pavilion"}]
    assert client.edit_calls == []


def test_past_images_use_edit_with_prompt():
    client = FakeOpenAI()
    past = [GeneratedImage(b"old1", "image/png"), GeneratedImage(b"old2", "image/png")]

    _gen(client).generate("make it dusk", past)

    call = client.edit_calls[0]
    assert call["prompt"] == "make it dusk"
    assert [f.read() for f in call["image"]] == [b"old1", b"old2"]
    assert client.generate_calls == []


def test_more_than_three_past_images_is_rejected():
    past = [GeneratedImage(b"x", "image/png")] * 4
    with pytest.raises(ValueError):
        _gen(FakeOpenAI()).generate("p", past)


def test_response_without_image_raises():
    with pytest.raises(ImageGenerationError):
        _gen(FakeOpenAI(_response(b64=None))).generate("p")


def test_model_and_limit_come_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "custom-image")
    monkeypatch.setenv("MAX_PAST_IMAGES", "1")
    client = FakeOpenAI()
    generator = ImageGeneratorService(client=client)

    generator.generate("p")
    assert client.generate_calls[0]["model"] == "custom-image"
    with pytest.raises(ValueError):
        generator.generate("p", [GeneratedImage(b"x", "image/png")] * 2)


def test_client_is_built_lazily_from_env_key_and_cached(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    generator = ImageGeneratorService()
    assert generator.client.api_key == "sk-env"
    assert generator.client is generator.client


def test_shared_service_is_cached():
    from backend.src.graph.tools.generate_image import generate_image as module

    module.get_image_generator_service.cache_clear()
    assert module.get_image_generator_service() is module.get_image_generator_service()
