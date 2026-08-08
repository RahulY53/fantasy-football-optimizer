"""End-to-end odds import, market fixture, player xPts, and blend test."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from fpl_optimizer.data.cache import JsonCache
from fpl_optimizer.data.fpl.client import FplClient
from fpl_optimizer.database.base import Database
from fpl_optimizer.database.forecast_repository import ForecastRepository
from fpl_optimizer.database.odds_repository import OddsRepository
from fpl_optimizer.odds.providers.csv_provider import CsvOddsProvider
from fpl_optimizer.odds.providers.manual_provider import ManualOddsProvider
from fpl_optimizer.services.forecast import ForecastService
from fpl_optimizer.services.markets import MarketService, OddsImportService
from fpl_optimizer.services.refresh import RefreshService


def test_market_pipeline_generates_independent_and_blended_xpts(
    tmp_path, bootstrap_payload, fixture_payload
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/bootstrap-static/"):
            return httpx.Response(200, json=bootstrap_payload)
        if request.url.path.endswith("/fixtures/"):
            return httpx.Response(200, json=fixture_payload)
        return httpx.Response(404)

    database = Database(f"sqlite:///{tmp_path / 'markets.db'}")
    database.create_schema()
    client = FplClient(
        "https://example.test/api",
        JsonCache(tmp_path / "cache"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    RefreshService(database, client).refresh(force=True)
    ForecastService(database).run(horizon=2)
    provider = ManualOddsProvider(
        1,
        "Test Book",
        datetime(2026, 8, 8, 12, tzinfo=UTC),
        1.8,
        3.8,
        4.8,
        1.8,
        2.05,
        1.75,
        2.1,
        1.65,
        2.25,
        2.6,
        1.55,
    )
    import_report = OddsImportService(database).import_provider(provider)
    scorer_report = OddsImportService(database).import_provider(
        CsvOddsProvider(
            "fixture_id,bookmaker,market,selection,decimal_odds,observed_at,player_id\n"
            "1,Test Book,anytime_goalscorer,score,2.8,2026-08-08T12:00:00Z,102\n"
            "1,Test Book,anytime_goalscorer,score,2.2,2026-08-08T12:00:00Z,202\n"
        )
    )
    market_report = MarketService(database).run()

    assert import_report.inserted == 11
    assert scorer_report.inserted == 2
    assert market_report.fixtures == 1
    assert market_report.player_forecasts == 4
    with database.session() as session:
        odds_repository = OddsRepository(session)
        dashboard = odds_repository.market_dashboard()
        assert len(dashboard) == 1
        assert dashboard[0]["Advanced markets"] == 3
        assert dashboard[0]["BTTS %"] is not None
        forecasts = ForecastRepository(session)
        statistical = forecasts.list_player_summaries(market_weight=0.0)
        market = forecasts.list_player_summaries(market_weight=1.0)
        covered = next(row for row in market if row["Market xPts"] is not None)
        baseline = next(row for row in statistical if row["Player ID"] == covered["Player ID"])
        assert baseline["Blended xPts"] == baseline["Stat xPts"]
        assert covered["Blended xPts"] == covered["Market xPts"]
        assert any(row["Goalscorer probability"] is not None for row in market)
    database.engine.dispose()
