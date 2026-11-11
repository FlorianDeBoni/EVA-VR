from functools import lru_cache

from openai import OpenAI

from backend.infra.AIClient import AIClient
from backend.src.graph.tools.search_web_images.schemas import ImageHit, RankedImage, Scores
from backend.src.settings.envManager import EnvKeyName, EnvManager


class ImageRankerService:
    """Scores image candidates with a vision LLM and keeps the best ones.

        ranker = get_image_ranker_service()
        top = ranker.rank("modern museum", "interior view", candidates)

    Model, batch size and top-k come from .env.backend (GPT_COMPLETION_MODEL,
    IMAGE_RANK_BATCH_SIZE, IMAGE_SEARCH_TOP_K) unless passed explicitly.
    The OpenAI client is created lazily and cached.
    """

    def __init__(
        self,
        client: OpenAI | None = None,
        model: str | None = None,
        batch_size: int | None = None,
        top_k: int | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._batch_size = batch_size
        self._top_k = top_k

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = AIClient.from_env().get_client()
        return self._client

    @property
    def model(self) -> str:
        return self._model or EnvManager.get_env_variable(EnvKeyName.KEY_GPT_COMPLETION_MODEL)

    @property
    def batch_size(self) -> int:
        # Thumbnails per vision call: keeps each request small and the scores consistent.
        if self._batch_size is not None:
            return self._batch_size
        return int(EnvManager.get_env_variable(EnvKeyName.KEY_IMAGE_RANK_BATCH_SIZE))

    @property
    def top_k(self) -> int:
        if self._top_k is not None:
            return self._top_k
        return int(EnvManager.get_env_variable(EnvKeyName.KEY_IMAGE_SEARCH_TOP_K))

    def _score_batch(self, query: str, criteria: str, batch: list[ImageHit]) -> list[RankedImage]:
        criteria = criteria or "image clearly shows what was requested"
        content = [
            {
                "type": "text",
                "text": (
                    f"Request: {query}\nCriteria: {criteria}\n"
                    f"Score each of the {len(batch)} images from 0 to 1 for relevance. "
                    "Images are numbered in order, starting at 0."
                ),
            }
        ]
        for i, hit in enumerate(batch):
            content.append({"type": "text", "text": f"Image {i}:"})
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": hit.thumbnail_url or hit.image_url, "detail": "low"},
                }
            )

        resp = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            response_format=Scores,
        )
        by_index = {s.index: s for s in resp.choices[0].message.parsed.scores}
        return [
            RankedImage(hit=hit, score=by_index[i].score, reason=by_index[i].reason)
            for i, hit in enumerate(batch)
            if i in by_index
        ]

    def rank(
        self,
        query: str,
        criteria: str,
        candidates: list[ImageHit],
        top_k: int | None = None,
    ) -> list[RankedImage]:
        """Score candidates against the query and return the best `top_k`, best first."""
        top_k = self.top_k if top_k is None else top_k
        size = self.batch_size

        ranked: list[RankedImage] = []
        for start in range(0, len(candidates), size):
            ranked += self._score_batch(query, criteria, candidates[start : start + size])

        ranked.sort(key=lambda r: r.score, reverse=True)
        return ranked[:top_k]


@lru_cache(maxsize=1)
def get_image_ranker_service() -> ImageRankerService:
    """Shared default service instance."""
    return ImageRankerService()
