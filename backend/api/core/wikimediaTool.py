# referenceImageTool.py

import requests
from typing import List, Optional, Dict
from urllib.parse import urlparse

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
WIKIMEDIA_API_URL = "https://commons.wikimedia.org/w/api.php"

HEADERS = {
    "User-Agent": (
        "DOKK1-2045/1.0 "
        "(https://eva-vr.hybridintelligence.eu; contact: florian.de.boni@gmail.com)"
    )
}

REQUEST_TIMEOUT = 10

ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
ALLOWED_IMAGE_DOMAIN = "upload.wikimedia.org"

# -------------------------------------------------------------------
# Validation helpers
# -------------------------------------------------------------------

def is_renderable_image_url(url: str) -> bool:
    url = url.lower().split("?")[0]
    return url.endswith(ALLOWED_EXTENSIONS)


def is_allowed_domain(url: str) -> bool:
    domain = urlparse(url).netloc.lower()
    return domain.endswith(ALLOWED_IMAGE_DOMAIN)


def validate_image_url(url: str) -> bool:
    """
    Validate existence + MIME type.
    Uses HEAD, falls back to GET when needed.
    """
    try:
        r = requests.head(
            url,
            allow_redirects=True,
            timeout=5,
            headers=HEADERS
        )

        if r.status_code == 200:
            return r.headers.get("Content-Type", "").startswith("image/")

        if r.status_code in (403, 405):
            r = requests.get(
                url,
                stream=True,
                timeout=5,
                headers=HEADERS
            )
            return (
                r.status_code == 200
                and r.headers.get("Content-Type", "").startswith("image/")
            )

    except requests.RequestException:
        return False

    return False

# -------------------------------------------------------------------
# Strategy 1: Wikipedia page–based reference image (PRIMARY)
# -------------------------------------------------------------------

def search_wikipedia_page(query: str) -> Optional[str]:
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": query,
        "srlimit": 1,
    }

    r = requests.get(
        WIKIPEDIA_API_URL,
        params=params,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT
    )
    r.raise_for_status()

    results = r.json().get("query", {}).get("search", [])
    if not results:
        return None

    return results[0]["title"]


def fetch_wikipedia_page_image(title: str) -> Optional[str]:
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "pageimages",
        "pithumbsize": 1600,
    }

    r = requests.get(
        WIKIPEDIA_API_URL,
        params=params,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT
    )
    r.raise_for_status()

    pages = r.json().get("query", {}).get("pages", {})

    for page in pages.values():
        thumb = page.get("thumbnail")
        if thumb:
            return thumb.get("source")

    return None


def fetch_wikipedia_reference_image(query: str) -> Optional[Dict]:
    print("[REFERENCE] Trying Wikipedia page image")

    title = search_wikipedia_page(query)
    if not title:
        return None

    url = fetch_wikipedia_page_image(title)
    if not url:
        return None

    if not is_allowed_domain(url):
        return None

    if not is_renderable_image_url(url):
        return None

    if not validate_image_url(url):
        return None

    return {
        "url": url,
        "source": "wikipedia",
        "title": title,
    }

# -------------------------------------------------------------------
# Strategy 2: Wikimedia Commons fallback (SECONDARY)
# -------------------------------------------------------------------

def search_commons_titles(query: str, limit: int = 15) -> List[str]:
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": f"{query} -filetype:pdf -filetype:djvu -filetype:tiff",
        "srnamespace": 6,
        "srlimit": limit,
    }

    r = requests.get(
        WIKIMEDIA_API_URL,
        params=params,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT
    )
    r.raise_for_status()

    return [i["title"] for i in r.json().get("query", {}).get("search", [])]


def fetch_commons_imageinfo(title: str) -> Optional[Dict]:
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
    }

    r = requests.get(
        WIKIMEDIA_API_URL,
        params=params,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT
    )
    r.raise_for_status()

    pages = r.json().get("query", {}).get("pages", {})

    for page in pages.values():
        info = page.get("imageinfo")
        if not info:
            continue

        url = info[0].get("url")
        if not url or not url.startswith("https://upload.wikimedia.org/"):
            continue

        return {
            "url": url,
            "source": "wikimedia",
            "title": title,
        }

    return None


def fetch_commons_reference_image(query: str) -> Optional[Dict]:
    print("[REFERENCE] Trying Wikimedia Commons")

    for title in search_commons_titles(query):
        image = fetch_commons_imageinfo(title)
        if not image:
            continue

        url = image["url"]

        if not is_renderable_image_url(url):
            continue

        if not validate_image_url(url):
            continue
        print("[REFERENCE] Found Wikimedia reference image:", url)
        return image

    return None

# -------------------------------------------------------------------
# Public tool entrypoint (USED BY LLM TOOL CALLS)
# -------------------------------------------------------------------

def fetch_reference_image(query: str) -> Optional[Dict]:
    """
    Fetch a real-world reference image.

    Strategy:
    1. Wikipedia page image (preferred)
    2. Wikimedia Commons file search (fallback)
    3. Return None if no reference exists
    """
    image = fetch_wikipedia_reference_image(query)
    if image:
        print("[REFERENCE] Found Wikipedia reference image:", image["url"])
        return image

    return fetch_commons_reference_image(query)
