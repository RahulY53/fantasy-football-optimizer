"""End-to-end strategy scoring and saved-profile persistence test."""

from __future__ import annotations

import httpx
import pytest

from fpl_optimizer.data.cache import JsonCache
from fpl_optimizer.data.fpl.client import FplClient
from fpl_optimizer.database.base import Database
from fpl_optimizer.scoring.presets import preset_profile
from fpl_optimizer.services.forecast import ForecastService
from fpl_optimizer.services.refresh import RefreshService
from fpl_optimizer.services.strategy import StrategyService


def test_strategy_scores_forecasts_and_saves_profile(
    tmp_path, bootstrap_payload, fixture_payload
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/bootstrap-static/"):
            return httpx.Response(200, json=bootstrap_payload)
        if request.url.path.endswith("/fixtures/"):
            return httpx.Response(200, json=fixture_payload)
        return httpx.Response(404)

    database = Database(f"sqlite:///{tmp_path / 'strategy.db'}")
    database.create_schema()
    client = FplClient(
        "https://example.test/api",
        JsonCache(tmp_path / "cache"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    RefreshService(database, client).refresh(force=True)
    ForecastService(database).run(horizon=2)
    service = StrategyService(database)
    selected = preset_profile("Balanced", "simple")

    scores = service.score(selected, market_weight=0.3)
    strategy_id = service.save(selected)
    saved = service.list_saved()

    assert len(scores) == 4
    assert scores == sorted(scores, key=lambda item: (-item.score, -item.horizon_xpts, item.player))
    assert scores[0].score == pytest.approx(
        sum(item.contribution for item in scores[0].contributions)
    )
    assert strategy_id > 0
    assert saved[0]["Name"] == "Balanced"
    assert saved[0]["Weights"] == selected.weights
    database.engine.dispose()
