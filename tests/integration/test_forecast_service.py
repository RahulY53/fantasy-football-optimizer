"""End-to-end six-Gameweek forecast persistence tests."""

from __future__ import annotations

import httpx

from fpl_optimizer.data.cache import JsonCache
from fpl_optimizer.data.fpl.client import FplClient
from fpl_optimizer.database.base import Database
from fpl_optimizer.database.forecast_repository import ForecastRepository
from fpl_optimizer.services.forecast import ForecastService
from fpl_optimizer.services.refresh import RefreshService


def test_forecast_handles_double_and_blank_gameweeks(
    tmp_path, bootstrap_payload, fixture_payload
) -> None:
    defender = next(
        player for player in bootstrap_payload["elements"] if player["element_type"] == 2
    )
    defender.update(
        {
            "defensive_contribution": 14,
            "clearances_blocks_interceptions": 10,
            "tackles": 4,
            "recoveries": 0,
        }
    )
    bootstrap_payload["events"].append(
        {
            "id": 3,
            "name": "Gameweek 3",
            "deadline_time": "2026-08-28T17:30:00Z",
            "is_current": False,
            "is_next": False,
            "finished": False,
        }
    )
    fixture_payload.append(
        {
            "id": 3,
            "event": 1,
            "team_h": 2,
            "team_a": 1,
            "kickoff_time": "2026-08-18T19:00:00Z",
            "team_h_difficulty": 4,
            "team_a_difficulty": 2,
            "started": False,
            "finished": False,
            "team_h_score": None,
            "team_a_score": None,
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/bootstrap-static/"):
            return httpx.Response(200, json=bootstrap_payload)
        if request.url.path.endswith("/fixtures/"):
            return httpx.Response(200, json=fixture_payload)
        return httpx.Response(404)

    database = Database(f"sqlite:///{tmp_path / 'forecast.db'}")
    database.create_schema()
    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = FplClient(
        "https://example.test/api",
        JsonCache(tmp_path / "cache"),
        http_client=http,
    )
    RefreshService(database, client).refresh(force=True)

    report = ForecastService(database).run(horizon=3)

    assert report.players == 4
    assert report.gameweeks == 3
    assert report.forecasts == 12
    with database.session() as session:
        repository = ForecastRepository(session)
        summaries = repository.list_player_summaries()
        details = repository.player_details(summaries[0]["Player ID"])
        assert details[0]["Fixtures"] == 2
        assert details[0]["Expected minutes"] > 90
        assert details[2]["Opponent"] == "Blank"
        assert details[2]["Stat xPts"] == 0
        assert "Defensive contribution xPts" in summaries[0]
        assert any(
            row["Defensive contribution"] > 0
            for summary in summaries
            for row in repository.player_details(summary["Player ID"])
        )
    database.engine.dispose()
