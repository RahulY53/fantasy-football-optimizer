"""Tests for live, cached, and offline FPL client behavior."""

from __future__ import annotations

import httpx

from fpl_optimizer.data.cache import JsonCache
from fpl_optimizer.data.fpl.client import FplClient


def test_client_fetches_and_then_uses_fresh_cache(tmp_path) -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json={"events": [], "teams": [], "elements": []})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = FplClient("https://example.test/api", JsonCache(tmp_path), http_client=http)

    first = client.bootstrap()
    second = client.bootstrap()

    assert not first.from_cache
    assert second.from_cache
    assert not second.stale
    assert requests == 1


def test_client_falls_back_to_stale_cache(tmp_path) -> None:
    cache = JsonCache(tmp_path)
    cache.put("/fixtures/", [{"id": 1}])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = FplClient("https://example.test/api", cache, http_client=http, max_attempts=1)

    result = client.fixtures(force=True)

    assert result.from_cache
    assert result.stale
    assert result.warning is not None
