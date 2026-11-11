import re
from functools import lru_cache
from typing import ClassVar

from ddgs import DDGS

from backend.src.graph.tools.search_web_images.schemas import ImageCategory, ImageHit
from backend.src.settings.envManager import EnvKeyName, EnvManager
from backend.src.settings.LogManager import LogManager


class ImageSearchService:
    """Web image search: query building, filtering, scoring and dedup in one place.

    Configure once, then call `search()` from anywhere:

        service = ImageSearchService(min_side=800)
        hits = service.search(["brutalist", "library"], [ImageCategory.INTERIOR])

    Scoring weights and blocked hosts come from .env.backend (KEYWORD_WEIGHT,
    CATEGORY_WEIGHT, BLOCKED_HOSTS) unless passed explicitly.
    Pass `ddgs` to inject a custom/fake search client (handy in tests).
    """

    # Words that signal a category, used both to build queries and to score results.
    CATEGORY_TERMS: ClassVar[dict[ImageCategory, tuple[str, ...]]] = {
        ImageCategory.BUILDING: ("architecture", "building", "facade", "exterior"),
        ImageCategory.INTERIOR: ("interior", "interior design", "room", "inside"),
        ImageCategory.INSTALLATION: ("installation", "art installation", "exhibition", "pavilion"),
    }

    def __init__(
        self,
        *,
        max_results: int = 20,
        per_query: int = 30,
        min_side: int = 600,
        min_score: float = 1.0,
        safesearch: str = "moderate",
        keyword_weight: float | None = None,
        category_weight: float | None = None,
        blocked_hosts: tuple[str, ...] | None = None,
        ddgs: DDGS | None = None,
    ) -> None:
        self.max_results = max_results
        self.per_query = per_query
        self.min_side = min_side
        self.min_score = min_score
        self.safesearch = safesearch
        self.keyword_weight = (
            keyword_weight
            if keyword_weight is not None
            else float(EnvManager.get_env_variable(EnvKeyName.KEY_KEYWORD_WEIGHT))
        )
        self.category_weight = (
            category_weight
            if category_weight is not None
            else float(EnvManager.get_env_variable(EnvKeyName.KEY_CATEGORY_WEIGHT))
        )
        # Hosts that mostly serve stock/vector/low-signal images.
        self.blocked_hosts = (
            blocked_hosts
            if blocked_hosts is not None
            else tuple(
                h.strip()
                for h in EnvManager.get_env_variable(EnvKeyName.KEY_BLOCKED_HOSTS).split(",")
                if h.strip()
            )
        )
        self._ddgs = ddgs
        self.logger = LogManager.get_logger(__name__)

    # ----- query building / scoring / filtering

    def build_queries(
        self, keywords: list[str], categories: list[ImageCategory]
    ) -> list[tuple[ImageCategory, str]]:
        """Combine the keywords with each category's main term into search queries."""
        base = " ".join(keywords).strip()
        return [(cat, f"{base} {self.CATEGORY_TERMS[cat][0]} photography") for cat in categories]

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", text.lower()))

    def score_result(self, result: dict, keywords: list[str], category: ImageCategory) -> float:
        """Score a raw ddgs result from its title and page URL (text only)."""
        haystack = self._tokens(f"{result.get('title', '')} {result.get('url', '')}")
        keyword_hits = sum(1 for kw in keywords for tok in self._tokens(kw) if tok in haystack)
        category_hits = sum(
            1 for term in self.CATEGORY_TERMS[category] if self._tokens(term) <= haystack
        )
        return keyword_hits * self.keyword_weight + category_hits * self.category_weight

    @staticmethod
    def _dimension(result: dict, key: str) -> int:
        """ddgs returns dimensions as strings from some backends."""
        try:
            return int(result.get(key) or 0)
        except TypeError, ValueError:
            return 0

    def _is_usable(self, result: dict, min_side: int) -> bool:
        if not result.get("image"):
            return False
        if any(host in result.get("url", "") for host in self.blocked_hosts):
            return False
        width, height = self._dimension(result, "width"), self._dimension(result, "height")
        return min(width, height) >= min_side

    # ----- public API

    def search(
        self,
        keywords: list[str],
        categories: list[ImageCategory] | None = None,
        *,
        max_results: int | None = None,
        min_side: int | None = None,
        min_score: float | None = None,
    ) -> list[ImageHit]:
        """Find web images of buildings, interiors or installations from keywords.

        Per-call `max_results`, `min_side` and `min_score` override the service defaults.

        Returns:
            Hits sorted by descending score, deduplicated by image URL.
        """
        max_results = self.max_results if max_results is None else max_results
        min_side = self.min_side if min_side is None else min_side
        min_score = self.min_score if min_score is None else min_score

        categories = categories or list(ImageCategory)
        ddgs = self._ddgs or DDGS()
        best: dict[str, ImageHit] = {}

        for category, query in self.build_queries(keywords, categories):
            try:
                results = ddgs.images(
                    query,
                    max_results=self.per_query,
                    safesearch=self.safesearch,
                )
            except Exception:  # noqa: BLE001 - one failing query must not sink the rest
                self.logger.warning("Image search failed for %r", query, exc_info=True)
                continue

            for r in results:
                if not self._is_usable(r, min_side):
                    continue
                score = self.score_result(r, keywords, category)
                if score < min_score:
                    continue
                hit = ImageHit(
                    title=r.get("title", ""),
                    image_url=r["image"],
                    thumbnail_url=r.get("thumbnail", ""),
                    page_url=r.get("url", ""),
                    width=self._dimension(r, "width"),
                    height=self._dimension(r, "height"),
                    category=category,
                    score=score,
                )
                if hit.image_url not in best or hit.score > best[hit.image_url].score:
                    best[hit.image_url] = hit

        return sorted(best.values(), key=lambda h: h.score, reverse=True)[:max_results]


@lru_cache(maxsize=1)
def get_image_search_service() -> ImageSearchService:
    """Shared default service instance."""
    return ImageSearchService()
