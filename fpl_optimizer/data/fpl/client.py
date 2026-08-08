"""Resilient public FPL HTTP client with offline cache fallback."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from fpl_optimizer.data.cache import CacheEntry, JsonCache

LOGGER = logging.getLogger(__name__)


class FplDataUnavailableError(RuntimeError):
    """Raised when neither the provider nor a valid cache can satisfy a request."""


@dataclass(frozen=True, slots=True)
class FetchResult:
    """Provider response paired with cache and freshness provenance."""

    endpoint: str
    entry: CacheEntry
    from_cache: bool
    stale: bool
    warning: str | None = None

    @property
    def payload(self) -> Any:
        """Return the decoded JSON payload."""

        return self.entry.payload


class FplClient:
    """Fetch public FPL JSON with bounded retry and cached fallback."""

    BOOTSTRAP_ENDPOINT = "/bootstrap-static/"
    FIXTURES_ENDPOINT = "/fixtures/"

    def __init__(
        self,
        base_url: str,
        cache: JsonCache,
        cache_ttl_seconds: int = 900,
        timeout_seconds: float = 15.0,
        http_client: httpx.Client | None = None,
        max_attempts: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.cache = cache
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_attempts = max(1, max_attempts)
        self._owns_client = http_client is None
        self.http = http_client or httpx.Client(
            timeout=timeout_seconds,
            headers={"User-Agent": "open-source-fpl-optimizer/0.1"},
        )

    def bootstrap(self, force: bool = False) -> FetchResult:
        """Fetch the bootstrap payload."""

        return self.fetch(self.BOOTSTRAP_ENDPOINT, force=force)

    def fixtures(self, force: bool = False) -> FetchResult:
        """Fetch the fixture payload."""

        return self.fetch(self.FIXTURES_ENDPOINT, force=force)

    def fetch(self, endpoint: str, force: bool = False) -> FetchResult:
        """Fetch JSON, preferring fresh cache and falling back to any valid cache."""

        cached = self.cache.latest(endpoint)
        if not force and cached and cached.is_fresh(self.cache_ttl_seconds):
            return FetchResult(endpoint, cached, from_cache=True, stale=False)

        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.http.get(f"{self.base_url}{endpoint}")
                response.raise_for_status()
                payload = response.json()
                entry = self.cache.put(endpoint, payload)
                return FetchResult(endpoint, entry, from_cache=False, stale=False)
            except (httpx.HTTPError, ValueError) as error:
                last_error = error
                LOGGER.warning(
                    "FPL request failed endpoint=%s attempt=%s/%s error=%s",
                    endpoint,
                    attempt,
                    self.max_attempts,
                    error,
                )
                if attempt < self.max_attempts:
                    time.sleep(0.1 * (2 ** (attempt - 1)))

        if cached is not None:
            warning = (
                f"Live refresh failed; using cached {endpoint} data from {cached.retrieved_at}."
            )
            return FetchResult(endpoint, cached, from_cache=True, stale=True, warning=warning)
        raise FplDataUnavailableError(
            f"FPL data unavailable for {endpoint} and no valid cache exists"
        ) from last_error

    def close(self) -> None:
        """Close an internally created HTTP client."""

        if self._owns_client:
            self.http.close()

    def __enter__(self) -> FplClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
