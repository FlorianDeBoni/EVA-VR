# wikimediaTool.py

import requests
from typing import List, Optional, Dict

# -------------------------------------------------------------------
# Wikimedia configuration
# -------------------------------------------------------------------

WIKIMEDIA_API_URL = "https://commons.wikimedia.org/w/api.php"

HEADERS = {
    "User-Agent": (
        "DOKK1-2045/1.0 "
        "(https://eva-vr.hybridintelligence.eu; contact: florian.de.boni@gmail.com)"
    )
}

REQUEST_TIMEOUT = 10


# -------------------------------------------------------------------
# Low-level helpers
# -------------------------------------------------------------------

def head_request(url: str) -> requests.Response:
    """
    Validate that a URL is reachable.
    """
    return requests.head(
        url,
        allow_redirects=True,
        timeout=5,
        headers=HEADERS
    )


# -------------------------------------------------------------------
# Step 1: Search for file titles
# -------------------------------------------------------------------

def search_wikimedia_titles(query: str, limit: int = 5) -> List[str]:
    """
    Search Wikimedia Commons for file titles matching the query.
    Returns a list of file titles (e.g. 'File:Dokk1 Aarhus - 2015.jpg').
    """
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": query,
        "srnamespace": 6,  # File namespace only
        "srlimit": limit,
    }

    r = requests.get(
        WIKIMEDIA_API_URL,
        params=params,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT
    )
    r.raise_for_status()

    data = r.json()
    search_results = data.get("query", {}).get("search", [])

    return [item["title"] for item in search_results]


# -------------------------------------------------------------------
# Step 2: Fetch image metadata for a given file title
# -------------------------------------------------------------------

def fetch_imageinfo(title: str) -> Optional[Dict]:
    """
    Fetch image URL and metadata for a given Wikimedia file title.
    """
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

    data = r.json()
    pages = data.get("query", {}).get("pages", {})

    for page in pages.values():
        imageinfo = page.get("imageinfo")
        if not imageinfo:
            continue

        info = imageinfo[0]
        meta = info.get("extmetadata", {})

        return {
            "url": info.get("url"),
            "author": meta.get("Artist", {}).get("value"),
            "license": meta.get("LicenseShortName", {}).get("value"),
            "source": "wikimedia",
            "title": title,
        }

    return None


# -------------------------------------------------------------------
# Public tool entrypoint (used by LLM tool calls)
# -------------------------------------------------------------------

def fetch_wikimedia_image(query: str) -> Optional[Dict]:
    """
    Fetch a single valid, publicly licensed image from Wikimedia Commons
    matching the query.

    Returns:
        {
            "url": str,
            "author": str | None,
            "license": str | None,
            "source": "wikimedia",
            "title": str
        }
        or None if nothing valid is found.
    """
    titles = search_wikimedia_titles(query)

    for title in titles:
        try:
            image = fetch_imageinfo(title)
            if not image or not image.get("url"):
                continue

            response = head_request(image["url"])
            if response.status_code == 200:
                return image

        except requests.RequestException:
            continue

    return None
