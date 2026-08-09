"""Integration tests for persisted cross-refresh player change detection."""

from __future__ import annotations

from copy import deepcopy

import httpx
import pytest
from sqlalchemy import select

from fpl_optimizer.data.cache import JsonCache
from fpl_optimizer.data.fpl.client import FplClient
from fpl_optimizer.database.base import Database
from fpl_optimizer.database.models import Player
from fpl_optimizer.services.changes import ChangeDetectionService
from fpl_optimizer.services.forecast import ForecastService
from fpl_optimizer.services.refresh import RefreshService


def test_changes_compare_latest_official_and_forecast_runs(
    tmp_path, bootstrap_payload, fixture_payload
) -> None:
    updated_bootstrap = deepcopy(bootstrap_payload)
    original = bootstrap_payload["elements"][0]
    updated = updated_bootstrap["elements"][0]
    updated["now_cost"] = int(original["now_cost"]) + 1
    updated["selected_by_percent"] = str(float(original["selected_by_percent"]) + 1.5)
    updated["status"] = "i"
    updated["news"] = "Late fitness test"
    updated["chance_of_playing_next_round"] = 25

    bootstrap_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal bootstrap_calls
        if request.url.path.endswith("/bootstrap-static/"):
            bootstrap_calls += 1
            payload = bootstrap_payload if bootstrap_calls == 1 else updated_bootstrap
            return httpx.Response(200, json=payload)
        if request.url.path.endswith("/fixtures/"):
            return httpx.Response(200, json=fixture_payload)
        return httpx.Response(404)

    database = Database(f"sqlite:///{tmp_path / 'changes.db'}")
    database.create_schema()
    client = FplClient(
        "https://example.test/api",
        JsonCache(tmp_path / "cache"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    refresh = RefreshService(database, client)
    forecast = ForecastService(database)
    changes = ChangeDetectionService(database)

    refresh.refresh(force=True)
    forecast.run()
    assert not changes.report().has_baseline

    with database.session() as session:
        first_id = session.scalar(
            select(Player.id).where(Player.fpl_id == int(original["id"]))
        )
    assert first_id is not None
    refresh.refresh(force=True)
    forecast.run()
    report = changes.report(watchlist_ids=frozenset({first_id}))

    assert report.has_baseline
    player_change = next(item for item in report.changes if item.player_id == first_id)
    assert player_change.watchlisted
    assert player_change.price_delta == pytest.approx(0.1)
    assert player_change.ownership_delta == pytest.approx(1.5)
    assert player_change.status_before != player_change.status
    assert player_change.news == "Late fitness test"
    assert {"Price", "Ownership", "Availability", "News"}.issubset(
        player_change.change_types
    )
    assert next(window for window in report.windows if window.source == "Official FPL").comparable
    assert next(
        window for window in report.windows if window.source == "Statistical forecast"
    ).comparable

    client.close()
    database.engine.dispose()
