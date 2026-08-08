"""Tests for public Team ID endpoint orchestration and Gameweek detection."""

from __future__ import annotations

import httpx
import pytest

from fpl_optimizer.data.cache import JsonCache
from fpl_optimizer.data.fpl.client import FplClient
from fpl_optimizer.data.fpl.team_service import (
    PublicFplTeamService,
    PublicTeamUnavailableError,
    latest_published_gameweek,
)


def test_latest_published_gameweek_uses_entry_and_finished_events() -> None:
    bootstrap = {"events": [{"id": 1, "finished": True}, {"id": 2, "finished": False}]}

    assert latest_published_gameweek(bootstrap, {"current_event": 2}) == 2


def test_public_team_service_fetches_all_team_endpoints(tmp_path) -> None:
    picks = [
        {
            "element": player_id,
            "position": position,
            "purchase_price": 50,
            "selling_price": 51,
            "is_captain": position == 1,
            "is_vice_captain": position == 2,
        }
        for position, player_id in enumerate(range(101, 116), start=1)
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        responses = {
            "/bootstrap-static/": {"events": [{"id": 3, "finished": True}]},
            "/entry/42/": {"id": 42, "current_event": 3, "name": "Test XI"},
            "/entry/42/event/3/picks/": {"picks": picks},
            "/entry/42/history/": {"current": [{"event": 3}]},
            "/entry/42/transfers/": [{"event": 3}],
        }
        payload = responses.get(request.url.path)
        return httpx.Response(200, json=payload) if payload is not None else httpx.Response(404)

    client = FplClient(
        "https://example.test",
        JsonCache(tmp_path / "cache"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_attempts=1,
    )

    result = PublicFplTeamService(client).fetch(42)

    assert result["gameweek"] == 3
    assert len(result["picks"]) == 15
    assert len(result["transfers"]) == 1
    client.close()


def test_public_team_service_reports_invalid_team(tmp_path) -> None:
    client = FplClient(
        "https://example.test",
        JsonCache(tmp_path / "cache"),
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(404))
        ),
        max_attempts=1,
    )

    with pytest.raises(PublicTeamUnavailableError, match="Team ID 999"):
        PublicFplTeamService(client).fetch(999)

    client.close()


def test_valid_preseason_entry_is_returned_without_inventing_picks(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/entry/42/":
            return httpx.Response(200, json={"id": 42, "current_event": None})
        if request.url.path == "/bootstrap-static/":
            return httpx.Response(200, json={"events": [{"id": 1, "finished": False}]})
        return httpx.Response(404)

    client = FplClient(
        "https://example.test",
        JsonCache(tmp_path / "cache"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_attempts=1,
    )

    result = PublicFplTeamService(client).fetch(42)

    assert result["gameweek"] == 0
    assert result["picks"] == []
    client.close()
