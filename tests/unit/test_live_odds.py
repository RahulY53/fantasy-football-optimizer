"""Tests for aliases, confidence matching, provider parsing, and cached fallback."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from fpl_optimizer.data.cache import JsonCache
from fpl_optimizer.domain.enums import OddsMarket, OddsSelection
from fpl_optimizer.odds.aliases import TeamAliases
from fpl_optimizer.odds.fixture_matcher import FplFixtureIdentity, VendorEvent, match_fixture
from fpl_optimizer.odds.providers.odds_api_io import OddsApiIoProvider
from fpl_optimizer.services.update_odds import parse_event_odds

ALIASES = Path(__file__).parents[2] / "config" / "team_aliases.yaml"


def test_fixture_matcher_uses_aliases_and_kickoff() -> None:
    kickoff = datetime(2026, 8, 8, 15, tzinfo=UTC)
    fixture = FplFixtureIdentity(10, "Man Utd", "Spurs", kickoff)
    event = VendorEvent(
        99,
        "Manchester United",
        "Tottenham Hotspur",
        kickoff + timedelta(minutes=5),
        "Premier League",
    )

    result = match_fixture(event, [fixture], TeamAliases(ALIASES))

    assert result is not None
    assert result.fixture_fpl_id == 10
    assert result.confidence > 99


def test_fixture_matcher_rejects_wrong_or_duplicate_fixture() -> None:
    kickoff = datetime(2026, 8, 8, 15, tzinfo=UTC)
    fixture = FplFixtureIdentity(10, "Arsenal", "Chelsea", kickoff)
    event = VendorEvent(99, "Arsenal", "Liverpool", kickoff, "Premier League")

    assert match_fixture(event, [fixture], TeamAliases(ALIASES)) is None


def test_odds_api_parser_keeps_bookmakers_and_supported_markets_separate() -> None:
    payload = {
        "id": 99,
        "date": "2026-08-08T15:00:00Z",
        "bookmakers": {
            "Book A": [
                {
                    "name": "ML",
                    "updatedAt": "2026-08-08T12:00:00Z",
                    "odds": [{"home": "2.0", "draw": "3.5", "away": "4.0"}],
                },
                {
                    "name": "Totals",
                    "updatedAt": "2026-08-08T12:00:00Z",
                    "odds": [{"hdp": 2.5, "over": "1.9", "under": "1.95"}],
                },
            ]
        },
    }

    quotes = parse_event_odds(payload, 10)

    assert len(quotes) == 5
    assert {quote.market for quote in quotes} == {
        OddsMarket.MATCH_RESULT,
        OddsMarket.TOTAL_GOALS_2_5,
    }
    assert {quote.selection for quote in quotes if quote.market is OddsMarket.MATCH_RESULT} == {
        OddsSelection.HOME,
        OddsSelection.DRAW,
        OddsSelection.AWAY,
    }


def test_odds_provider_uses_cached_fallback_without_exposing_key(tmp_path) -> None:
    responses = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal responses
        responses += 1
        if responses == 1:
            return httpx.Response(200, json=[{"id": 1}], headers={"x-ratelimit-remaining": "9"})
        return httpx.Response(503)

    cache = JsonCache(tmp_path / "odds-cache")
    provider = OddsApiIoProvider(
        "secret-key",
        cache,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        cache_ttl_seconds=3600,
    )

    assert provider.get_events(force=True) == [{"id": 1}]
    assert provider.get_events(force=True) == [{"id": 1}]
    assert provider.last_from_cache
    assert "secret-key" not in str(list((tmp_path / "odds-cache").rglob("*")))
    provider.close()


def test_odds_provider_falls_back_when_multi_endpoint_is_unavailable(tmp_path) -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/v3/odds/multi":
            return httpx.Response(403)
        if request.url.path == "/v3/odds":
            return httpx.Response(
                200,
                json={
                    "id": int(request.url.params["eventId"]),
                    "bookmakers": {},
                },
            )
        return httpx.Response(404)

    provider = OddsApiIoProvider(
        "secret-key",
        JsonCache(tmp_path / "fallback-cache"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.get_event_odds([10, 11], force=True)

    assert [item["id"] for item in result] == [10, 11]
    assert paths == ["/v3/odds/multi", "/v3/odds", "/v3/odds"]
    provider.close()


def test_odds_provider_retries_with_account_selected_bookmakers(tmp_path) -> None:
    requested_bookmakers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v3/odds/multi":
            books = request.url.params["bookmakers"]
            requested_bookmakers.append(books)
            if books != "SingBet":
                return httpx.Response(400)
            return httpx.Response(200, json=[{"id": 10, "bookmakers": {}}])
        if request.url.path == "/v3/bookmakers/selected":
            return httpx.Response(200, json={"bookmakers": ["SingBet"]})
        return httpx.Response(404)

    provider = OddsApiIoProvider(
        "secret-key",
        JsonCache(tmp_path / "selected-cache"),
        bookmakers="Bet365,Unibet,Pinnacle",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.get_event_odds([10], force=True)

    assert result == [{"id": 10, "bookmakers": {}}]
    assert requested_bookmakers == ["Bet365,Unibet,Pinnacle", "SingBet"]
    assert provider.bookmakers == "SingBet"
    provider.close()
