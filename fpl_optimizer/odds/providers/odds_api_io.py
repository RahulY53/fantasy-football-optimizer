"""Cached server-side connector for Odds-API.io v3."""

from __future__ import annotations

from typing import Any

import httpx

from fpl_optimizer.data.cache import JsonCache


class OddsApiIoError(RuntimeError):
    """Raised when live and cached provider data are both unavailable."""


class OddsApiIoHttpError(OddsApiIoError):
    """Safe HTTP failure that never includes the credential-bearing request URL."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class OddsApiIoProvider:
    """Fetch EPL events and multi-event odds without exposing the API key."""

    name = "odds_api_io"

    def __init__(
        self,
        api_key: str,
        cache: JsonCache,
        *,
        base_url: str = "https://api.odds-api.io/v3",
        bookmakers: str = "Bet365,Unibet,Pinnacle",
        cache_ttl_seconds: int = 3600,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.cache = cache
        self.base_url = base_url.rstrip("/")
        self.bookmakers = bookmakers
        self.cache_ttl_seconds = cache_ttl_seconds
        self.http = http_client or httpx.Client(timeout=15.0)
        self._owns_client = http_client is None
        self.last_from_cache = False
        self.requests_made = 0
        self.rate_limit_remaining: int | None = None

    def get_events(self, force: bool = False) -> list[dict[str, Any]]:
        """Fetch only pending English Premier League football events."""

        payload = self._get(
            "/events",
            "odds-api-io/epl-events",
            {
                "sport": "football",
                "league": "england-premier-league",
                "status": "pending",
            },
            force,
        )
        if not isinstance(payload, list):
            raise OddsApiIoError("Odds provider returned malformed events")
        return [item for item in payload if isinstance(item, dict)]

    def get_event_odds(
        self, event_ids: list[int], force: bool = False
    ) -> list[dict[str, Any]]:
        """Fetch odds in provider-supported batches of ten events."""

        results: list[dict[str, Any]] = []
        effective_bookmakers = self.bookmakers
        for offset in range(0, len(event_ids), 10):
            batch = event_ids[offset : offset + 10]
            try:
                payload = self._get_odds_batch(batch, effective_bookmakers, force)
            except OddsApiIoHttpError as error:
                if error.status_code == 400:
                    discovered = self._discover_bookmakers(force)
                    if discovered and discovered != effective_bookmakers:
                        effective_bookmakers = discovered
                        self.bookmakers = discovered
                        try:
                            payload = self._get_odds_batch(
                                batch, effective_bookmakers, force
                            )
                        except OddsApiIoHttpError as retry_error:
                            if retry_error.status_code not in {400, 403, 404}:
                                raise
                            payload = self._get_individual_odds(
                                batch, effective_bookmakers, force
                            )
                    else:
                        payload = self._get_individual_odds(
                            batch, effective_bookmakers, force
                        )
                elif error.status_code in {403, 404}:
                    payload = self._get_individual_odds(
                        batch, effective_bookmakers, force
                    )
                else:
                    raise
            if not isinstance(payload, list):
                raise OddsApiIoError("Odds provider returned malformed prices")
            results.extend(item for item in payload if isinstance(item, dict))
        return results

    def test_connection(self) -> bool:
        """Validate credentials and EPL event access without bypassing the cache."""

        self.get_events(force=False)
        return True

    def close(self) -> None:
        if self._owns_client:
            self.http.close()

    def _get_individual_odds(
        self, event_ids: list[int], bookmakers: str, force: bool
    ) -> list[dict[str, Any]]:
        """Compatibility fallback when an account cannot use multi-event odds."""

        results: list[dict[str, Any]] = []
        first_error: OddsApiIoHttpError | None = None
        for event_id in event_ids:
            try:
                payload = self._get(
                    "/odds",
                    f"odds-api-io/odds/event/{event_id}/{bookmakers}",
                    {"eventId": str(event_id), "bookmakers": bookmakers},
                    force,
                )
            except OddsApiIoHttpError as error:
                if error.status_code == 404:
                    continue
                first_error = first_error or error
                continue
            if isinstance(payload, dict):
                results.append(payload)
        if not results and first_error is not None:
            raise first_error
        return results

    def _get_odds_batch(
        self, event_ids: list[int], bookmakers: str, force: bool
    ) -> Any:
        key = (
            "odds-api-io/odds/"
            + "-".join(map(str, event_ids))
            + "/"
            + bookmakers
        )
        return self._get(
            "/odds/multi",
            key,
            {
                "eventIds": ",".join(map(str, event_ids)),
                "bookmakers": bookmakers,
            },
            force,
        )

    def _discover_bookmakers(self, force: bool) -> str:
        """Read account-selected bookmakers, falling back to active supported names."""

        selected: list[str] = []
        try:
            payload = self._get(
                "/bookmakers/selected",
                "odds-api-io/bookmakers/selected",
                {},
                force,
            )
            selected = _bookmaker_names(payload)
        except OddsApiIoError:
            pass
        if selected:
            return ",".join(selected[:10])
        try:
            payload = self._get(
                "/bookmakers", "odds-api-io/bookmakers/active", {}, force
            )
            supported = _bookmaker_names(payload, active_only=True)
        except OddsApiIoError:
            return self.bookmakers
        configured = [name.strip() for name in self.bookmakers.split(",") if name.strip()]
        supported_lookup = {name.lower(): name for name in supported}
        valid = [
            supported_lookup[name.lower()]
            for name in configured
            if name.lower() in supported_lookup
        ]
        return ",".join(valid[:10]) if valid else ",".join(supported[:3])

    def _get(
        self,
        path: str,
        cache_key: str,
        params: dict[str, str],
        force: bool,
    ) -> Any:
        cached = self.cache.latest(cache_key)
        if not force and cached is not None and cached.is_fresh(self.cache_ttl_seconds):
            self.last_from_cache = True
            return cached.payload
        if not self.api_key:
            if cached is not None:
                self.last_from_cache = True
                return cached.payload
            raise OddsApiIoError("Set FPL_OPTIMIZER_ODDS_API_KEY in .env to enable live odds")
        try:
            response = self.http.get(
                f"{self.base_url}{path}", params={"apiKey": self.api_key, **params}
            )
            self.requests_made += 1
            response.raise_for_status()
            payload = response.json()
            remaining = response.headers.get("x-ratelimit-remaining")
            self.rate_limit_remaining = int(remaining) if remaining else None
            self.cache.put(cache_key, payload)
            self.last_from_cache = False
            return payload
        except httpx.HTTPStatusError as error:
            if cached is not None:
                self.last_from_cache = True
                return cached.payload
            status = error.response.status_code
            messages = {
                400: "Odds-API.io rejected the odds request or bookmaker selection (HTTP 400)",
                401: "Odds-API.io rejected the API key (HTTP 401)",
                403: "The Odds-API.io account cannot access this odds endpoint (HTTP 403)",
                404: "Odds-API.io has no prices for the requested event (HTTP 404)",
                429: "Odds-API.io request quota or rate limit was reached (HTTP 429)",
            }
            message = messages.get(status, f"Odds-API.io request failed (HTTP {status})")
            raise OddsApiIoHttpError(status, message) from error
        except (httpx.RequestError, ValueError) as error:
            if cached is not None:
                self.last_from_cache = True
                return cached.payload
            raise OddsApiIoError(
                "Could not reach Odds-API.io and no cached odds snapshot exists"
            ) from error


def _bookmaker_names(payload: Any, *, active_only: bool = False) -> list[str]:
    """Parse documented lists and common selected-bookmaker response wrappers."""

    if isinstance(payload, list):
        names: list[str] = []
        for item in payload:
            if isinstance(item, str) and item.strip():
                names.append(item.strip())
            elif isinstance(item, dict):
                name = item.get("name")
                if (
                    isinstance(name, str)
                    and name.strip()
                    and (not active_only or item.get("active", True))
                ):
                    names.append(name.strip())
        return list(dict.fromkeys(names))
    if isinstance(payload, dict):
        for key in (
            "bookmakers",
            "selected",
            "selectedBookmakers",
            "selected_bookmakers",
            "data",
            "items",
        ):
            if key in payload:
                return _bookmaker_names(payload[key], active_only=active_only)
        return [
            str(name)
            for name, enabled in payload.items()
            if isinstance(name, str) and bool(enabled)
        ]
    return []
