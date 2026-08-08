"""Integration coverage for atomic imports, leakage guards, and saved runs."""

from __future__ import annotations

from datetime import timedelta

import httpx
from sqlalchemy import select

from fpl_optimizer.data.cache import JsonCache
from fpl_optimizer.data.fpl.client import FplClient
from fpl_optimizer.database.backtest_repository import BacktestRepository
from fpl_optimizer.database.base import Database
from fpl_optimizer.database.models import Gameweek, Player, PlayerForecast
from fpl_optimizer.services.backtesting import BacktestService
from fpl_optimizer.services.forecast import ForecastService
from fpl_optimizer.services.refresh import RefreshService


def test_backtest_import_ignores_post_deadline_forecast_and_persists_run(
    tmp_path, bootstrap_payload, fixture_payload
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/bootstrap-static/"):
            return httpx.Response(200, json=bootstrap_payload)
        if request.url.path.endswith("/fixtures/"):
            return httpx.Response(200, json=fixture_payload)
        return httpx.Response(404)

    database = Database(f"sqlite:///{tmp_path / 'backtesting.db'}")
    database.create_schema()
    client = FplClient(
        "https://example.test/api",
        JsonCache(tmp_path / "cache"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    RefreshService(database, client).refresh(force=True)
    ForecastService(database).run(horizon=2)
    with database.session() as session:
        player = session.scalar(select(Player).order_by(Player.id))
        gameweek = session.scalar(select(Gameweek).order_by(Gameweek.fpl_id))
        assert player is not None and gameweek is not None
        original = session.scalar(
            select(PlayerForecast).where(
                PlayerForecast.player_id == player.id,
                PlayerForecast.gameweek_id == gameweek.id,
            )
        )
        assert original is not None
        original_xpts = original.stat_xpts
        session.add(
            PlayerForecast(
                player_id=original.player_id,
                gameweek_id=original.gameweek_id,
                model_version_id=original.model_version_id,
                prediction_at=gameweek.deadline_at + timedelta(hours=1),
                input_cutoff_at=gameweek.deadline_at + timedelta(hours=1),
                expected_minutes=90,
                appearance_xpts=0,
                goal_xpts=0,
                assist_xpts=0,
                clean_sheet_xpts=0,
                save_xpts=0,
                bonus_xpts=0,
                deduction_xpts=0,
                stat_xpts=99,
                fixture_count=1,
                opponent_summary="Leaked",
                confidence="High",
                component_json="{}",
            )
        )
        player_fpl_id = player.fpl_id
        gameweek_fpl_id = gameweek.fpl_id

    service = BacktestService(database)
    imported = service.import_csv(
        "player_id,gameweek,actual_points,actual_minutes\n"
        f"{player_fpl_id},{gameweek_fpl_id},5,90\n",
        "integration.csv",
    )
    with database.session() as session:
        observations = BacktestRepository(session).observations()
    report = service.run()

    assert imported == 1
    assert observations[0].stat_xpts == original_xpts
    assert observations[0].stat_xpts != 99
    assert report.run_id == 1
    assert service.recent()[0]["Observations"] == 1
    client.close()
    database.engine.dispose()
