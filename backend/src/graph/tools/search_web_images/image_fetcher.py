import io
import ipaddress
import socket
from functools import lru_cache
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image, UnidentifiedImageError

from backend.src.graph.tools.generate_image.schemas import GeneratedImage
from backend.src.settings.LogManager import LogManager


class ImageFetcherService:
    """Downloads a web image and normalizes it for storage and for the models.

        image = get_image_fetcher_service().fetch("https://example.com/a.webp")

    The URLs come from a web search, so they are untrusted: only http(s) to public
    addresses is allowed (redirects are checked hop by hop), the download is capped and
    the bytes must decode as an image. The result is a JPEG whose longest side is at
    most `max_side`, which keeps the base64 small and every format the models accept.
    `fetch` returns None instead of raising when an image cannot be used.
    """

    MAX_REDIRECTS = 3

    def __init__(
        self,
        client: httpx.Client | None = None,
        max_bytes: int = 10_000_000,
        max_side: int = 1024,
        timeout: float = 10.0,
    ) -> None:
        self._client = client
        self.max_bytes = max_bytes
        self.max_side = max_side
        self.timeout = timeout
        self.logger = LogManager.get_logger(__name__)

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout, follow_redirects=False)
        return self._client

    @staticmethod
    def _is_public(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        try:
            infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
        except OSError:
            return False
        return all(ipaddress.ip_address(info[4][0]).is_global for info in infos)

    def _download(self, url: str) -> bytes | None:
        for _ in range(self.MAX_REDIRECTS + 1):
            if not self._is_public(url):
                self.logger.warning("Refusing to fetch %s", url)
                return None
            with self.client.stream("GET", url) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers.get("location", ""))
                    continue
                if response.status_code != 200:
                    return None
                content = bytearray()
                for chunk in response.iter_bytes():
                    content += chunk
                    if len(content) > self.max_bytes:
                        return None
                return bytes(content)
        return None

    def fetch(self, url: str) -> GeneratedImage | None:
        """Return the image at `url` (JPEG, at most `max_side` px), or None if unusable."""
        try:
            raw = self._download(url)
            if raw is None:
                return None
            with Image.open(io.BytesIO(raw)) as image:
                image = image.convert("RGB")
                image.thumbnail((self.max_side, self.max_side))
                out = io.BytesIO()
                image.save(out, format="JPEG", quality=85)
        except (
            httpx.HTTPError,
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombError,
        ):
            self.logger.warning("Could not fetch image %s", url, exc_info=True)
            return None
        return GeneratedImage(out.getvalue(), "image/jpeg")


@lru_cache(maxsize=1)
def get_image_fetcher_service() -> ImageFetcherService:
    """Shared default service instance."""
    return ImageFetcherService()
