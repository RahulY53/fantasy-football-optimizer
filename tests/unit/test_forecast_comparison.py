"""Tests for future fixture and expected-points comparison analytics."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fpl_optimizer.analytics.forecast_comparison import (
    build_forecast_comparison,
    fixture_comparison_rows,
    forecast_export_rows,
)
from fpl_optimizer.analytics.player_dataset import build_player_dataset


def test_forecast_comparison_aligns_weeks_and_calculates_cumulative_xpts() -> None:
    players = (_record(1, "Bukayo Saka", "ARS"), _record(2, "Cole Palmer", "CHE"))
    comparison = build_forecast_comparison(
        players,
        {
            1: [_detail(25, 5.0, "CHE (H)"), _detail(26, 7.0, "LEE (A)")],
            2: [_detail(25, 6.0, "ARS (A)"), _detail(26, 4.0, "NEW (H)")],
        },
        3,
    )

    assert comparison.gameweeks == ("Gameweek 25", "Gameweek 26")
    assert comparison.series[0].points[1].cumulative_xpts == pytest.approx(12.0)
    assert comparison.series[1].points[0].market_xpts == pytest.approx(6.2)
    assert comparison.forecasted_at == datetime(2026, 8, 8, 12, tzinfo=UTC)


def test_fixture_and_export_rows_preserve_raw_values() -> None:
    comparison = build_forecast_comparison(
        (_record(1, "Bukayo Saka", "ARS"),),
        {1: [_detail(25, 5.0, "CHE (H)")]},
        1,
    )

    fixture = fixture_comparison_rows(comparison)[0]
    exported = forecast_export_rows(comparison)[0]

    assert fixture["Gameweek 25"] == "CHE (H) · A 3.2 · D 4.1"
    assert exported["Blended xPts"] == pytest.approx(5.0)
    assert exported["Attacking Difficulty"] == pytest.approx(3.2)
    assert exported["Full Name"] == "Bukayo Saka"


def test_forecast_comparison_rejects_unsupported_horizon() -> None:
    with pytest.raises(ValueError, match="one of"):
        build_forecast_comparison((), {}, 2)


def _record(player_id: int, name: str, team: str):
    return build_player_dataset(
        [
            {
                "Player ID": player_id,
                "Full Name": name,
                "Display Name": name,
                "Web Name": name.split()[-1],
                "Name Search": name.casefold(),
                "Team": team,
                "Position": "MID",
                "Price": 8.0,
                "Ownership %": 20.0,
                "Status": "a",
                "News": "",
                "Points": 100,
                "Form": 6.0,
                "Points/game": 5.0,
                "Updated": datetime(2026, 8, 8, tzinfo=UTC),
            }
        ],
        [],
        [],
    )[0]


def _detail(gameweek: int, xpts: float, opponent: str) -> dict[str, object]:
    return {
        "Gameweek ID": gameweek,
        "Gameweek number": gameweek,
        "Gameweek": f"Gameweek {gameweek}",
        "Opponent": opponent,
        "Fixtures": 1,
        "Attacking difficulty": 3.2,
        "Defensive difficulty": 4.1,
        "Expected minutes": 80.0,
        "Stat xPts": xpts - 0.2,
        "Market xPts": xpts + 0.2,
        "Blended xPts": xpts,
        "Confidence": "High",
        "Forecasted": datetime(2026, 8, 8, 12, tzinfo=UTC),
    }
