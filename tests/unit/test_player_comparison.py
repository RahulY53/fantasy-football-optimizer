"""Tests for reusable player comparison and radar normalization."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fpl_optimizer.analytics.comparison import (
    available_radar_metrics,
    comparison_rows,
    default_radar_metrics,
    radar_profiles,
)
from fpl_optimizer.analytics.player_dataset import PlayerAnalyticsRecord, build_player_dataset


def test_same_position_radar_uses_full_position_universe_and_inverts_risk() -> None:
    records = _records()
    selected = records[:2]

    profiles = radar_profiles(
        selected,
        records,
        ("blended_xpts", "expected_minutes", "risk"),
        "Same Position",
    )

    arsenal = {metric.key: metric for metric in profiles[0].metrics}
    chelsea = {metric.key: metric for metric in profiles[1].metrics}
    assert arsenal["blended_xpts"].score == pytest.approx(0.0)
    assert chelsea["blended_xpts"].score == pytest.approx(50.0)
    assert arsenal["risk"].label == "Reliability"
    assert arsenal["risk"].score == pytest.approx(100.0)
    assert chelsea["risk"].score == pytest.approx(50.0)
    assert arsenal["blended_xpts"].formatted_value == "4.0"


def test_selected_player_universe_changes_percentiles_without_changing_raw_values() -> None:
    records = _records()
    selected = records[:2]

    profiles = radar_profiles(
        selected,
        records,
        ("blended_xpts", "expected_minutes", "risk"),
        "Selected Players",
    )

    assert profiles[1].metrics[0].score == pytest.approx(100.0)
    assert profiles[1].metrics[0].raw_value == 6.0


def test_position_defaults_and_comparison_rows_use_available_raw_metrics() -> None:
    records = _records()
    selected = records[:2]

    available = available_radar_metrics(selected)
    defaults = default_radar_metrics(selected)
    rows = comparison_rows(selected)

    assert "goal_xpts" in available
    assert "goal_xpts" in defaults
    assert "assist_xpts" in defaults
    assert rows[0]["Full Name"] == "Arsenal Midfielder"
    assert rows[0]["Start probability %"] == 70.0


def test_same_position_universe_rejects_cross_position_comparison() -> None:
    records = _records()
    defender = _record(4, "Arsenal Defender", "ARS", "DEF", 5.0, 72.0, 25.0)

    with pytest.raises(ValueError, match="Same Position"):
        radar_profiles(
            (records[0], defender),
            (*records, defender),
            ("blended_xpts", "expected_minutes", "risk"),
            "Same Position",
        )


def _records() -> tuple[PlayerAnalyticsRecord, ...]:
    return (
        _record(1, "Arsenal Midfielder", "ARS", "MID", 4.0, 70.0, 20.0),
        _record(2, "Chelsea Midfielder", "CHE", "MID", 6.0, 80.0, 40.0),
        _record(3, "Liverpool Midfielder", "LIV", "MID", 8.0, 90.0, 60.0),
    )


def _record(
    player_id: int,
    name: str,
    team: str,
    position: str,
    blended_xpts: float,
    expected_minutes: float,
    risk: float,
) -> PlayerAnalyticsRecord:
    return build_player_dataset(
        [
            {
                "Player ID": player_id,
                "Full Name": name,
                "Display Name": name,
                "Web Name": name,
                "Name Search": name.casefold(),
                "Team": team,
                "Position": position,
                "Price": 8.0,
                "Ownership %": 15.0,
                "Status": "a",
                "News": "",
                "Points": 50,
                "Form": 5.0,
                "Points/game": 4.0,
                "Updated": datetime(2026, 8, 8, tzinfo=UTC),
            }
        ],
        [
            {
                "Player ID": player_id,
                "Opponent": "NFO (H)",
                "Expected minutes": expected_minutes,
                "Start probability %": expected_minutes,
                "Stat xPts": blended_xpts - 0.2,
                "Market xPts": blended_xpts + 0.2,
                "Blended xPts": blended_xpts,
                "Goal probability %": 30.0,
                "Goal xPts": blended_xpts * 0.30,
                "Assist xPts": blended_xpts * 0.20,
                "Clean sheet xPts": blended_xpts * 0.10,
                "Save xPts": 0.0,
                "Bonus xPts": blended_xpts * 0.05,
                "Attacking xPts": blended_xpts * 0.50,
                "3GW xPts": blended_xpts * 3,
                "5GW xPts": blended_xpts * 5,
                "6GW xPts": blended_xpts * 6,
                "Forecast confidence": "High",
            }
        ],
        [
            {
                "Player ID": player_id,
                "Value": blended_xpts / 8.0,
                "Risk": risk,
                "Optimization Score": blended_xpts * 10,
            }
        ],
    )[0]
