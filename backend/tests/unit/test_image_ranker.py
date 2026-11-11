from types import SimpleNamespace

import pytest

from backend.src.graph.tools.search_web_images.image_ranker import ImageRankerService
from backend.src.graph.tools.search_web_images.schemas import ImageCategory, ImageHit


@pytest.fixture(autouse=True)
def batch_size(monkeypatch):
    monkeypatch.setenv("IMAGE_RANK_BATCH_SIZE", "10")


def _hit(n: int) -> ImageHit:
    return ImageHit(
        title=f"img {n}",
        image_url=f"https://img/{n}.jpg",
        thumbnail_url=f"https://thumb/{n}.jpg",
        page_url=f"https://example.com/{n}",
        width=1200,
        height=800,
        category=ImageCategory.INTERIOR,
        score=1.0,
    )


class FakeLLM:
    """Scores image i with scores[i] and records the calls it received."""

    def __init__(self, scores: list[float]) -> None:
        self._scores = scores
        self.calls: list[list[int]] = []
        self.beta = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(parse=self._parse))
        )

    def _parse(self, *, model, messages, response_format):
        n = sum(1 for m in messages[0]["content"] if m["type"] == "image_url")
        offset = sum(len(c) for c in self.calls)
        self.calls.append(list(range(offset, offset + n)))
        scores = [
            SimpleNamespace(index=i, score=self._scores[offset + i], reason=f"r{offset + i}")
            for i in range(n)
        ]
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(parsed=SimpleNamespace(scores=scores)))
            ]
        )


def test_rank_images_returns_top_k_best_first_across_batches():
    candidates = [_hit(i) for i in range(12)]
    scores = [0.1] * 12
    scores[11] = 0.9  # lands in the second batch
    scores[2] = 0.7

    ranker = ImageRankerService(client=FakeLLM(scores), model="m")
    ranked = ranker.rank("q", "c", candidates, top_k=2)

    assert [r.hit.image_url for r in ranked] == ["https://img/11.jpg", "https://img/2.jpg"]
    assert ranked[0].reason == "r11"


def test_rank_images_handles_no_candidates():
    assert ImageRankerService(client=FakeLLM([]), model="m").rank("q", "c", []) == []


def test_rank_images_reads_model_from_env(monkeypatch):
    seen = {}
    llm = FakeLLM([0.5])
    original = llm._parse

    def spy(*, model, messages, response_format):
        seen["model"] = model
        return original(model=model, messages=messages, response_format=response_format)

    llm.beta.chat.completions.parse = spy
    monkeypatch.setenv("GPT_COMPLETION_MODEL", "env-model")
    ImageRankerService(client=llm).rank("q", "c", [_hit(0)])
    assert seen["model"] == "env-model"


def test_client_is_built_lazily_from_env_key_and_cached(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    ranker = ImageRankerService()
    assert ranker.client.api_key == "sk-env"
    assert ranker.client is ranker.client


def test_defaults_come_from_env(monkeypatch):
    monkeypatch.setenv("IMAGE_RANK_BATCH_SIZE", "4")
    monkeypatch.setenv("IMAGE_SEARCH_TOP_K", "2")
    ranker = ImageRankerService()
    assert (ranker.batch_size, ranker.top_k) == (4, 2)


def test_shared_service_is_cached():
    from backend.src.graph.tools.search_web_images import image_ranker

    image_ranker.get_image_ranker_service.cache_clear()
    assert image_ranker.get_image_ranker_service() is image_ranker.get_image_ranker_service()
