import requests

def search_wikimedia(query: str, limit: int = 5):
    url = "https://commons.wikimedia.org/w/api.php"

    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrlimit": limit,
        "gsrnamespace": 6,  # File namespace only
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
    }

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    results = []

    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        info = page.get("imageinfo", [{}])[0]
        meta = info.get("extmetadata", {})

        results.append({
            "url": info.get("url"),
            "author": meta.get("Artist", {}).get("value"),
            "license": meta.get("LicenseShortName", {}).get("value"),
            "source": "wikimedia"
        })

    return results

def head_request(url: str):
    return requests.head(
        url,
        allow_redirects=True,
        timeout=5
    )

def fetch_wikimedia_image(query: str):
    results = search_wikimedia(query)

    for image in results:
        url = image.get("url")
        if not url:
            continue

        try:
            if head_request(url).status_code == 200:
                return image
        except requests.RequestException:
            continue

    return None
