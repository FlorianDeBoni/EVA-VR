from backend.src.graph.tools.search_web_images import search_web
from backend.src.graph.tools.search_web_images.schemas import ImageCategory
from backend.src.graph.tools.search_web_images.search_web import ImageSearchService

svc = ImageSearchService()


def _result(title="", url="https://example.com/a", image="https://img/1.jpg", w=1200, h=800):
    return {"title": title, "url": url, "image": image, "thumbnail": "t", "width": w, "height": h}


def test_build_queries_one_per_category():
    queries = svc.build_queries(
        ["concrete", "library"], [ImageCategory.INTERIOR, ImageCategory.BUILDING]
    )
    assert queries == [
        (ImageCategory.INTERIOR, "concrete library interior photography"),
        (ImageCategory.BUILDING, "concrete library architecture photography"),
    ]


def test_score_rewards_keyword_and_category_matches():
    good = _result("Concrete library interior design")
    bad = _result("Cute puppies")
    kw = ["concrete", "library"]
    assert svc.score_result(good, kw, ImageCategory.INTERIOR) > svc.score_result(
        bad, kw, ImageCategory.INTERIOR
    )
    assert svc.score_result(bad, kw, ImageCategory.INTERIOR) == 0


def test_search_filters_dedupes_and_sorts(monkeypatch):
    results = [
        _result("Concrete library interior", image="https://img/a.jpg"),
        _result("Concrete library interior", image="https://img/a.jpg"),  # duplicate
        _result("Concrete library", image="https://img/b.jpg"),
        _result("Concrete library interior", image="https://img/small.jpg", w=100, h=100),
        _result(
            "Concrete library interior", url="https://pinterest.com/x", image="https://img/p.jpg"
        ),
        _result("Unrelated cat", image="https://img/cat.jpg"),
    ]

    class FakeDDGS:
        def images(self, *args, **kwargs):
            return results

    monkeypatch.setattr(search_web, "DDGS", FakeDDGS)
    hits = svc.search(["concrete", "library"], [ImageCategory.INTERIOR])

    assert [h.image_url for h in hits] == ["https://img/a.jpg", "https://img/b.jpg"]


def test_failing_query_is_skipped(monkeypatch):
    class FailingDDGS:
        def images(self, *args, **kwargs):
            raise RuntimeError("rate limited")

    monkeypatch.setattr(search_web, "DDGS", FailingDDGS)
    assert svc.search(["loft"]) == []


def test_string_dimensions_from_backend_are_handled(monkeypatch):
    class StringDimsDDGS:
        def images(self, *args, **kwargs):
            return [_result("Concrete library", w="1000", h="667")]

    monkeypatch.setattr(search_web, "DDGS", StringDimsDDGS)
    hits = svc.search(["concrete", "library"], [ImageCategory.BUILDING])
    assert (hits[0].width, hits[0].height) == (1000, 667)


def test_service_uses_injected_client_and_per_call_overrides():
    calls = []

    class FakeClient:
        def images(self, query, **kwargs):
            calls.append((query, kwargs))
            return [_result("Concrete library", image="https://img/b.jpg", w=300, h=300)]

    service = ImageSearchService(per_query=5, ddgs=FakeClient())
    assert service.search(["concrete", "library"], [ImageCategory.BUILDING]) == []
    hits = service.search(["concrete", "library"], [ImageCategory.BUILDING], min_side=200)

    assert [h.image_url for h in hits] == ["https://img/b.jpg"]
    assert calls[0][1] == {"max_results": 5, "safesearch": "moderate"}


def test_weights_and_blocked_hosts_come_from_env(monkeypatch):
    monkeypatch.setenv("KEYWORD_WEIGHT", "5")
    monkeypatch.setenv("CATEGORY_WEIGHT", "0")
    monkeypatch.setenv("BLOCKED_HOSTS", "evil., spam.")
    service = ImageSearchService()

    assert service.blocked_hosts == ("evil.", "spam.")
    assert service.score_result(_result("loft"), ["loft"], ImageCategory.BUILDING) == 5
    assert not service._is_usable(_result(url="https://evil.com/x"), 100)


def test_shared_service_is_cached():
    search_web.get_image_search_service.cache_clear()
    assert search_web.get_image_search_service() is search_web.get_image_search_service()


def test_failing_query_is_logged(monkeypatch):
    class FailingDDGS:
        def images(self, *args, **kwargs):
            raise RuntimeError("rate limited")

    warnings = []
    service = ImageSearchService(ddgs=FailingDDGS())
    monkeypatch.setattr(service.logger, "warning", lambda *a, **k: warnings.append(a))

    assert service.search(["loft"], [ImageCategory.BUILDING]) == []
    assert len(warnings) == 1
