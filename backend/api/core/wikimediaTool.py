# wikimediaTool.py

import requests
from typing import List, Optional, Dict
from urllib.parse import urlparse

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

ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
ALLOWED_IMAGE_DOMAINS = (
    "upload.wikimedia.org",
)

# -------------------------------------------------------------------
# Validation helpers (STRICT)
# -------------------------------------------------------------------

def is_allowed_image_domain(url: str) -> bool:
    """
    Hard gate: only allow Wikimedia Commons image CDN.
    """
    domain = urlparse(url).netloc.lower()
    return any(domain.endswith(d) for d in ALLOWED_IMAGE_DOMAINS)


def is_renderable_image_url(url: str) -> bool:
    """
    Ensure the URL points to a browser-renderable raster image.
    """
    url = url.lower().split("?")[0]
    return url.endswith(ALLOWED_EXTENSIONS)


def validate_image_url(url: str) -> bool:
    """
    Validate that the image is accessible and has a correct MIME type.
    Uses HEAD first, falls back to GET for CDNs that block HEAD.
    """
    try:
        # 1️⃣ Try HEAD first
        response = requests.head(
            url,
            allow_redirects=True,
            timeout=5,
            headers=HEADERS
        )

        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            return content_type.startswith("image/")

        # 2️⃣ Fallback for CDNs blocking HEAD
        if response.status_code in (403, 405):
            response = requests.get(
                url,
                stream=True,
                timeout=5,
                headers=HEADERS
            )
            content_type = response.headers.get("Content-Type", "")
            return response.status_code == 200 and content_type.startswith("image/")

    except requests.RequestException:
        return False

    return False


# -------------------------------------------------------------------
# Step 1: Search for file titles
# -------------------------------------------------------------------

def search_wikimedia_titles(query: str, limit: int = 15) -> List[str]:

    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": f'{query} -filetype:pdf -filetype:djvu -filetype:tiff',
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

    data = r.json()
    search_results = data.get("query", {}).get("search", [])

    return [item["title"] for item in search_results]


# -------------------------------------------------------------------
# Step 2: Fetch image metadata
# -------------------------------------------------------------------
def fetch_imageinfo(title: str) -> Optional[Dict]:
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
        imageinfo = page.get("imageinfo")
        if not imageinfo:
            continue

        info = imageinfo[0]
        url = info.get("url")

        # 🔒 ABSOLUTE RULE: Wikimedia CDN only
        if not url or not url.startswith("https://upload.wikimedia.org/"):
            continue


        meta = info.get("extmetadata", {})

        return {
            "url": url,
            "author": meta.get("Artist", {}).get("value"),
            "license": meta.get("LicenseShortName", {}).get("value"),
            "source": "wikimedia",
            "title": title,
        }

    return None


# -------------------------------------------------------------------
# Public tool entrypoint (USED BY LLM TOOL CALLS)
# -------------------------------------------------------------------

def fetch_wikimedia_image(query: str) -> Optional[Dict]:
    """
    Returns ONE guaranteed frontend-safe Wikimedia image or None.
    """
    print("Fetching Wikimedia image")
    titles = search_wikimedia_titles(query)

    print(f"Found {len(titles)} candidate titles")

    for title in titles:
        try:
            image = fetch_imageinfo(title)
            if not image or not image.get("url"):
                continue

            url = image["url"]
            
            # 🔒 1️⃣ HARD DOMAIN GATE (NO EXCEPTIONS)
            if not is_allowed_image_domain(url):
                print(f"[WIKIMEDIA] Rejected external URL: {url}")
                continue

            # 2️⃣ Extension allowlist
            if not is_renderable_image_url(url):
                print(f"[WIKIMEDIA] Rejected external URL: {url}")
                continue

            # 3️⃣ Accessibility + MIME validation
            if not validate_image_url(url):
                print(f"[WIKIMEDIA] Rejected external URL: {url}")
                continue

            print(f"[WIKIMEDIA] Selected image URL: {url}")
            # ✅ Guaranteed frontend-safe image
            return image

        except requests.RequestException:
            continue

    return None
