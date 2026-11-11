from backend.src.graph.tools.search_web_images import tool as tool_module
from backend.src.graph.tools.search_web_images.schemas import ImageHit, RankedImage
from backend.src.graph.tools.search_web_images.tool import search_web_images


def _ranked(n):
    hit = ImageHit(f"t{n}", f"https://img/{n}.jpg", "th", "https://p", 800, 600, "building", 1.0)
    return RankedImage(hit=hit, score=1 - n / 10, reason=f"r{n}")


def test_tool_schema_exposes_query_and_criteria():
    props = search_web_images.args_schema.model_json_schema()["properties"]
    assert set(props) == {"query", "criteria"}


def test_tool_searches_ranks_and_returns_top(monkeypatch):
    seen = {}

    class FakeService:
        def search(self, keywords):
            seen["keywords"] = keywords
            return ["c1", "c2"]

    class FakeRanker:
        def rank(self, query, criteria, candidates):
            seen.update(query=query, criteria=criteria, candidates=candidates)
            return [_ranked(0), _ranked(1)]

    monkeypatch.setattr(tool_module, "get_image_search_service", lambda: FakeService())
    monkeypatch.setattr(tool_module, "get_image_ranker_service", lambda: FakeRanker())

    out = search_web_images.invoke({"query": "modern museum", "criteria": "interior"})

    assert seen == {
        "keywords": ["modern", "museum"],
        "query": "modern museum",
        "criteria": "interior",
        "candidates": ["c1", "c2"],
    }
    assert [r["image_url"] for r in out] == ["https://img/0.jpg", "https://img/1.jpg"]
    assert out[0]["reason"] == "r0"
