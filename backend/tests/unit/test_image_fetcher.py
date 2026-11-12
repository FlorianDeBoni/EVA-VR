import io

import httpx
import pytest
from PIL import Image

from backend.src.graph.tools.search_web_images import image_fetcher as module
from backend.src.graph.tools.search_web_images.image_fetcher import ImageFetcherService


def _image_bytes(size=(2000, 1000), fmt="PNG"):
    buffer = io.BytesIO()
    Image.new("RGB", size, "red").save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def public_hosts(monkeypatch):
    monkeypatch.setattr(
        ImageFetcherService, "_is_public", staticmethod(lambda url: "private" not in url)
    )


def _service(handler, **kwargs):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return ImageFetcherService(client=client, **kwargs)


def test_fetch_returns_a_resized_jpeg():
    service = _service(lambda request: httpx.Response(200, content=_image_bytes()), max_side=512)

    image = service.fetch("https://example.com/a.png")

    assert image.mime_type == "image/jpeg"
    with Image.open(io.BytesIO(image.data)) as result:
        assert result.format == "JPEG"
        assert max(result.size) == 512


def test_fetch_follows_redirects_to_public_hosts():
    def handler(request):
        if request.url.path == "/a":
            return httpx.Response(302, headers={"location": "/b.png"})
        return httpx.Response(200, content=_image_bytes((10, 10)))

    assert _service(handler).fetch("https://example.com/a") is not None


def test_fetch_refuses_a_redirect_to_a_private_host():
    def handler(request):
        return httpx.Response(302, headers={"location": "http://private.local/x"})

    assert _service(handler).fetch("https://example.com/a") is None


def test_fetch_refuses_private_hosts_without_any_request():
    called = []
    service = _service(lambda request: called.append(request) or httpx.Response(200))

    assert service.fetch("http://private.local/a.png") is None
    assert called == []


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(404),
        httpx.Response(200, content=b"<html>not an image</html>"),
        httpx.Response(200, content=_image_bytes()),  # larger than max_bytes below
    ],
)
def test_fetch_returns_none_for_unusable_images(response):
    assert _service(lambda request: response, max_bytes=100).fetch("https://example.com/a") is None


def test_fetch_returns_none_on_network_errors():
    def handler(request):
        raise httpx.ConnectError("boom")

    assert _service(handler).fetch("https://example.com/a") is None


def test_fetch_gives_up_after_too_many_redirects():
    service = _service(lambda request: httpx.Response(302, headers={"location": "/again"}))

    assert service.fetch("https://example.com/a") is None


@pytest.mark.parametrize(
    ("url", "expected"),
    [("ftp://example.com/a", False), ("file:///etc/passwd", False), ("http:///nohost", False)],
)
def test_only_http_urls_with_a_host_are_public(monkeypatch, url, expected):
    monkeypatch.undo()
    assert ImageFetcherService._is_public(url) is expected


def test_loopback_is_not_public(monkeypatch):
    monkeypatch.undo()
    assert ImageFetcherService._is_public("http://127.0.0.1/a.png") is False


def test_shared_service_is_cached():
    module.get_image_fetcher_service.cache_clear()
    assert module.get_image_fetcher_service() is module.get_image_fetcher_service()


def test_the_http_client_is_built_lazily_and_cached():
    service = ImageFetcherService()

    assert service.client is service.client
    assert service.client.follow_redirects is False


def test_an_unresolvable_host_is_not_public(monkeypatch):
    monkeypatch.undo()

    def fail(*args, **kwargs):
        raise OSError("no such host")

    monkeypatch.setattr(module.socket, "getaddrinfo", fail)

    assert ImageFetcherService._is_public("https://nowhere.invalid/a.png") is False
