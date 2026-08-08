"""Tests for the shared player analytics dataset and filter system."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fpl_optimizer.analytics.filters import PlayerFilterSpec, filter_players
from fpl_optimizer.analytics.metrics import METRICS, metric_definition
from fpl_optimizer.analytics.player_dataset import build_player_dataset


def test_dataset_joins_precomputed_metrics_and_normalizes_direction() -> None:
    records = build_player_dataset(
        [
            _player(1, "Martin Ødegaard", "ARS", "MID", 8.0, 18.0),
            _player(2, "Cole Palmer", "CHE", "MID", 9.5, 42.0),
        ],
        [_forecast(1, 75.0, 5.5, 24.0), _forecast(2, 82.0, 7.0, 29.0)],
        [_score(1, 30.0, 62.0), _score(2, 55.0, 88.0)],
    )

    arsenal, chelsea = records
    assert arsenal.full_name == "Martin Ødegaard"
    assert arsenal.xpts_5gw == 24.0
    assert arsenal.start_probability is None
    assert chelsea.normalized["blended_xpts"] == pytest.approx(100.0)
    assert arsenal.normalized["risk"] == pytest.approx(100.0)
    assert chelsea.normalized["risk"] == pytest.approx(0.0)


def test_combined_filters_apply_to_one_shared_dataset() -> None:
    records = build_player_dataset(
        [
            _player(1, "Martin Ødegaard", "ARS", "MID", 8.0, 18.0),
            _player(2, "William Saliba", "ARS", "DEF", 6.0, 25.0),
            _player(3, "Cole Palmer", "CHE", "MID", 9.5, 42.0),
        ],
        [
            _forecast(1, 75.0, 5.5, 24.0),
            _forecast(2, 70.0, 4.0, 18.0),
            _forecast(3, 82.0, 7.0, 29.0),
        ],
        [_score(1, 30.0, 62.0), _score(2, 20.0, 58.0), _score(3, 55.0, 88.0)],
    )

    filtered = filter_players(
        records,
        PlayerFilterSpec(
            search="odegaard",
            teams=("ARS",),
            positions=("MID",),
            price_range=(5.0, 8.0),
            ownership_range=(0.0, 20.0),
            minimum_expected_minutes=70.0,
            minimum_xpts_5gw=20.0,
            maximum_risk=40.0,
            minimum_optimization_score=60.0,
            available_only=True,
        ),
    )

    assert [record.player_id for record in filtered] == [1]


def test_metric_registry_is_unique_and_explains_negative_metrics() -> None:
    assert len(METRICS) == len(set(METRICS))
    risk = metric_definition("risk")
    assert not risk.higher_is_better
    assert risk.radar_label == "Reliability"


def _player(
    player_id: int,
    name: str,
    team: str,
    position: str,
    price: float,
    ownership: float,
) -> dict[str, object]:
    return {
        "Player ID": player_id,
        "Full Name": name,
        "Display Name": name,
        "Web Name": name.split()[-1],
        "Name Search": name.casefold().replace("ø", "o"),
        "Team": team,
        "Position": position,
        "Price": price,
        "Ownership %": ownership,
        "Status": "a",
        "News": "",
        "Points": 50,
        "Form": 5.0,
        "Points/game": 4.0,
        "Updated": datetime(2026, 8, 8, tzinfo=UTC),
    }


def _forecast(
    player_id: int, minutes: float, blended_xpts: float, five_week_xpts: float
) -> dict[str, object]:
    return {
        "Player ID": player_id,
        "Opponent": "NFO (H)",
        "Expected minutes": minutes,
        "Stat xPts": blended_xpts - 0.2,
        "Market xPts": blended_xpts + 0.2,
        "Blended xPts": blended_xpts,
        "3GW xPts": five_week_xpts * 0.6,
        "5GW xPts": five_week_xpts,
        "6GW xPts": five_week_xpts * 1.2,
        "Forecast confidence": "High",
    }


def _score(player_id: int, risk: float, score: float) -> dict[str, object]:
    return {
        "Player ID": player_id,
        "Value": score / 10,
        "Risk": risk,
        "Optimization Score": score,
    }
