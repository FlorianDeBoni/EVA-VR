from langchain_core.tools import tool

from backend.src.graph.tools.search_web_images.image_ranker import get_image_ranker_service
from backend.src.graph.tools.search_web_images.schemas import SearchWebImagesInput
from backend.src.graph.tools.search_web_images.search_web import get_image_search_service


@tool("search_web_images", args_schema=SearchWebImagesInput)
def search_web_images(query: str, criteria: str = "") -> list[dict]:
    """Search the web for architecture images and return the best matches.

    Finds candidate images of buildings, interiors and installations for the query,
    has a vision model score them against the criteria, and returns the top results
    (best first) with image_url, page_url, score and a short reason.
    """
    candidates = get_image_search_service().search(keywords=query.split())
    ranked = get_image_ranker_service().rank(query, criteria, candidates)
    return [
        {
            "title": r.hit.title,
            "image_url": r.hit.image_url,
            "thumbnail_url": r.hit.thumbnail_url,
            "page_url": r.hit.page_url,
            "width": r.hit.width,
            "height": r.hit.height,
            "score": r.score,
            "reason": r.reason,
        }
        for r in ranked
    ]
