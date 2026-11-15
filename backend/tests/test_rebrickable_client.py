import httpx
import pytest

from app.services.rebrickable import RebrickableClient, RebrickableImportError


def test_parts_fetcher_follows_all_pages() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.path.endswith("/parts/") and request.url.params.get("page") is None:
            return httpx.Response(
                200,
                json={"results": [{"id": 1}], "next": "https://example.test/api/v3/lego/sets/75978-1/parts/?page=2"},
            )
        return httpx.Response(200, json={"results": [{"id": 2}], "next": None})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="https://example.test") as http_client:
        client = RebrickableClient("test-key", http_client)
        parts = client.fetch_all_pages("/api/v3/lego/sets/75978-1/parts/?inc_minifig_parts=0")

    assert parts == [{"id": 1}, {"id": 2}]
    assert len(requests) == 2


def test_fetcher_rejects_incomplete_api_response() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={"next": None}))
    with httpx.Client(transport=transport, base_url="https://example.test") as http_client:
        client = RebrickableClient("test-key", http_client)
        with pytest.raises(RebrickableImportError, match="vollständige Ergebnisliste"):
            client.fetch_all_pages("/api/v3/lego/sets/75978-1/parts/")
