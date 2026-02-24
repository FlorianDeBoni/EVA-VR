from typing import List, Dict
from serpapi import GoogleSearch
from decouple import config

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

SERPAPI_KEY = config("SERPAPI_KEY")
MAX_CANDIDATES = 5
ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def is_renderable_image_url(url: str) -> bool:
    return url.lower().split("?")[0].endswith(ALLOWED_EXTENSIONS)

def is_http_url(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")

# -------------------------------------------------------------------
# SerpAPI (Google Images)
# -------------------------------------------------------------------

def fetch_serpapi_candidates(query: str) -> List[Dict]:
    search = GoogleSearch({
        "api_key": SERPAPI_KEY,
        "engine": "google_images",
        "q": query,
        "hl": "en",
        "gl": "us",
        "safe": "active",
    })

    results = search.get_dict()
    images = results.get("images_results", [])

    candidates = []

    for img in images:
        url = img.get("original")
        if not url:
            continue
        if not is_http_url(url):
            continue
        if not is_renderable_image_url(url):
            continue

        candidates.append({
            "id": f"SERP_{hash(url)}",
            "url": url,
            "source": "google_images",
            "title": img.get("title") or img.get("name"),
            "source_page": img.get("link"),
            "confidence": "google images"
        })

        if len(candidates) >= MAX_CANDIDATES:
            break
    print(f"Fetched {len(candidates)} candidates from SerpAPI for query: {query}")
    print(candidates[0])
    print()
    return candidates

# -------------------------------------------------------------------
# Public tool entrypoint (UNCHANGED CONTRACT)
# -------------------------------------------------------------------

def fetch_reference_images(query: str) -> List[Dict]:
    """
    Fetch multiple plausible reference image candidates.

    Returns:
        List of candidate images.
        The LLM MUST choose the most relevant one or reject all.
    """
    print(f"Fetching reference images for query: {query}")
    return fetch_serpapi_candidates(query)
