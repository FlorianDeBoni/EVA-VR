from backend.src.graph.tools.generate_image.schemas import GeneratedImage
from backend.src.graph.tools.search_web_images import finder as module
from backend.src.graph.tools.search_web_images.finder import WebImageFinderService
from backend.src.graph.tools.search_web_images.schemas import ImageHit, RankedImage


def _ranked(n):
    hit = ImageHit(
        f"t{n}", f"https://img/{n}.jpg", "", f"https://page/{n}", 800, 600, "interior", 1
    )
    return RankedImage(hit=hit, score=1 - n / 10, reason=f"r{n}")


class FakeSearch:
    def __init__(self):
        self.keywords = None

    def search(self, keywords):
        self.keywords = keywords
        return ["candidate"]


class FakeRanker:
    def __init__(self, total=9):
        self.total = total
        self.seen = None

    def rank(self, query, criteria, candidates, top_k=None):
        self.seen = (query, criteria, candidates, top_k)
        return [_ranked(n) for n in range(top_k or 3)][: self.total]


class FakeFetcher:
    def __init__(self, broken=()):
        self.broken = set(broken)
        self.fetched = []

    def fetch(self, url):
        self.fetched.append(url)
        return None if url in self.broken else GeneratedImage(url.encode(), "image/jpeg")


def test_search_ranks_the_candidates_of_the_query():
    search, ranker = FakeSearch(), FakeRanker()
    finder = WebImageFinderService(search_service=search, ranker=ranker)

    result = finder.search("modern museum", "interior")

    assert search.keywords == ["modern", "museum"]
    assert ranker.seen == ("modern museum", "interior", ["candidate"], None)
    assert len(result) == 3


def test_download_skips_broken_links_and_still_returns_the_requested_count():
    ranker = FakeRanker()
    fetcher = FakeFetcher(broken={"https://img/0.jpg", "https://img/2.jpg"})
    finder = WebImageFinderService(search_service=FakeSearch(), ranker=ranker, fetcher=fetcher)

    result = finder.download("studio", "", 3)

    assert ranker.seen[3] == 3 * WebImageFinderService.POOL_FACTOR
    assert [d.ranked.hit.image_url for d in result] == [f"https://img/{n}.jpg" for n in (1, 3, 4)]
    assert result[0].data == b"https://img/1.jpg" and result[0].mime_type == "image/jpeg"
    # It stops downloading as soon as it has enough images.
    assert len(fetcher.fetched) == 5


def test_download_returns_fewer_images_when_not_enough_are_usable():
    fetcher = FakeFetcher(broken={f"https://img/{n}.jpg" for n in range(9)})
    finder = WebImageFinderService(
        search_service=FakeSearch(), ranker=FakeRanker(), fetcher=fetcher
    )

    assert finder.download("studio", "", 3) == []


def test_services_are_built_lazily_and_shared_finder_is_cached(monkeypatch):
    built = []
    for name in ("search", "ranker", "fetcher"):
        attr = {
            "search": "get_image_search_service",
            "ranker": "get_image_ranker_service",
            "fetcher": "get_image_fetcher_service",
        }[name]
        monkeypatch.setattr(module, attr, lambda n=name: built.append(n) or n)
    finder = WebImageFinderService()
    assert not built

    assert (finder.search_service, finder.ranker, finder.fetcher) == ("search", "ranker", "fetcher")
    assert finder.fetcher is finder.fetcher and built == ["search", "ranker", "fetcher"]

    module.get_web_image_finder_service.cache_clear()
    assert module.get_web_image_finder_service() is module.get_web_image_finder_service()
