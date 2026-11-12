from functools import lru_cache

from backend.src.graph.tools.search_web_images.image_fetcher import (
    ImageFetcherService,
    get_image_fetcher_service,
)
from backend.src.graph.tools.search_web_images.image_ranker import (
    ImageRankerService,
    get_image_ranker_service,
)
from backend.src.graph.tools.search_web_images.schemas import DownloadedImage, RankedImage
from backend.src.graph.tools.search_web_images.search_web import (
    ImageSearchService,
    get_image_search_service,
)


class WebImageFinderService:
    """Search, rank and (optionally) download web images: the one entry point for the tools.

        finder = get_web_image_finder_service()
        ranked = finder.search("modern museum", "interior view")        # URLs only
        files = finder.download("modern museum", "interior view", 3)    # 3 usable files

    `search` finds candidates and has a vision model rank them. `download` does the same,
    then fetches the best ones, skipping the links that are dead or not images, so it
    still returns `count` images when some of the top results are broken.
    The three underlying services are created lazily; pass them to replace them (tests).
    """

    # Candidates ranked per image wanted, to absorb the downloads that fail.
    POOL_FACTOR = 3

    def __init__(
        self,
        search_service: ImageSearchService | None = None,
        ranker: ImageRankerService | None = None,
        fetcher: ImageFetcherService | None = None,
    ) -> None:
        self._search_service = search_service
        self._ranker = ranker
        self._fetcher = fetcher

    @property
    def search_service(self) -> ImageSearchService:
        if self._search_service is None:
            self._search_service = get_image_search_service()
        return self._search_service

    @property
    def ranker(self) -> ImageRankerService:
        if self._ranker is None:
            self._ranker = get_image_ranker_service()
        return self._ranker

    @property
    def fetcher(self) -> ImageFetcherService:
        if self._fetcher is None:
            self._fetcher = get_image_fetcher_service()
        return self._fetcher

    def search(self, query: str, criteria: str = "", top_k: int | None = None) -> list[RankedImage]:
        """Return the best web images for the query, best first (`top_k` defaults to the env)."""
        candidates = self.search_service.search(keywords=query.split())
        return self.ranker.rank(query, criteria, candidates, top_k=top_k)

    def download(self, query: str, criteria: str, count: int) -> list[DownloadedImage]:
        """Return up to `count` downloaded images, best first (fewer if not enough are usable)."""
        downloaded: list[DownloadedImage] = []
        for ranked in self.search(query, criteria, top_k=count * self.POOL_FACTOR):
            if len(downloaded) == count:
                break
            image = self.fetcher.fetch(ranked.hit.image_url)
            if image is not None:
                downloaded.append(DownloadedImage(ranked, image.data, image.mime_type))
        return downloaded


@lru_cache(maxsize=1)
def get_web_image_finder_service() -> WebImageFinderService:
    """Shared default service instance."""
    return WebImageFinderService()
