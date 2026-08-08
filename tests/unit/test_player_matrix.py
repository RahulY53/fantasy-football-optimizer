"""Tests for raw-axis player matrix calculations and presets."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fpl_optimizer.analytics.matrix import (
    MATRIX_PRESETS,
    available_matrix_presets,
    build_matrix,
)
from fpl_optimizer.analytics.player_dataset import PlayerAnalyticsRecord, build_player_dataset


def test_value_matrix_uses_raw_medians_and_assigns_all_quadrants() -> None:
    records = _records()
    preset = MATRIX_PRESETS["value_map"]

    analysis = build_matrix(
        records,
        preset.x_metric,
        preset.y_metric,
        labels=preset.quadrant_labels,
    )

    assert analysis.x_reference == pytest.approx(7.5)
    assert analysis.y_reference == pytest.approx(20.0)
    assert {point.player_id: point.quadrant for point in analysis.points} == {
        1: "upper_left",
        2: "upper_right",
        3: "lower_left",
        4: "lower_right",
    }
    assert analysis.insights[0].label == "HIGH RETURN / LOWER PRICE"
    assert analysis.insights[0].players[0].full_name == "Player One"
    assert analysis.points[0].x_value == 5.0
    assert analysis.points[0].x_formatted == "£5.0m"


def test_position_and_custom_references_remain_in_raw_units() -> None:
    records = _records()

    position = build_matrix(
        records,
        "price",
        "xpts_5gw",
        "Position Median",
        reference_position="DEF",
    )
    custom = build_matrix(
        records,
        "price",
        "xpts_5gw",
        "Custom",
        custom_x=8.0,
        custom_y=18.0,
    )

    assert position.x_reference == pytest.approx(7.5)
    assert position.y_reference == pytest.approx(12.5)
    assert custom.x_reference == 8.0
    assert custom.y_reference == 18.0


def test_derived_matrix_metrics_are_transparent_ratios() -> None:
    player = _records()[0]

    assert player.xpts_per_million == pytest.approx(5.0)
    assert player.xpts_per_90 == pytest.approx(5.0)
    assert player.market_edge == pytest.approx(0.5)


def test_market_presets_require_market_axis_coverage() -> None:
    records = tuple(
        _record(index, f"No Market {index}", "MID", 5.0, 20.0, 50.0, market=False)
        for index in (1, 2)
    )

    preset_keys = {preset.key for preset in available_matrix_presets(records)}

    assert "value_map" in preset_keys
    assert "market_model" not in preset_keys
    assert "market_disagreement" not in preset_keys


def test_matrix_rejects_identical_axes() -> None:
    with pytest.raises(ValueError, match="different metrics"):
        build_matrix(_records(), "price", "price")


def _records() -> tuple[PlayerAnalyticsRecord, ...]:
    return (
        _record(1, "Player One", "MID", 5.0, 25.0, 80.0),
        _record(2, "Player Two", "MID", 10.0, 30.0, 90.0),
        _record(3, "Player Three", "DEF", 6.0, 15.0, 60.0),
        _record(4, "Player Four", "DEF", 9.0, 10.0, 50.0),
    )


def _record(
    player_id: int,
    name: str,
    position: str,
    price: float,
    five_week_xpts: float,
    score: float,
    *,
    market: bool = True,
) -> PlayerAnalyticsRecord:
    blended = 5.0
    return build_player_dataset(
        [
            {
                "Player ID": player_id,
                "Full Name": name,
                "Display Name": name,
                "Web Name": name,
                "Name Search": name.casefold(),
                "Team": "ARS" if player_id % 2 else "CHE",
                "Position": position,
                "Price": price,
                "Ownership %": float(player_id * 10),
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
                "Expected minutes": 90.0,
                "Stat xPts": blended - 0.5,
                "Market xPts": blended if market else None,
                "Market edge": 0.5 if market else None,
                "Blended xPts": blended,
                "Goal xPts": 1.0,
                "Assist xPts": 1.0,
                "3GW xPts": five_week_xpts * 0.6,
                "5GW xPts": five_week_xpts,
                "6GW xPts": five_week_xpts * 1.2,
            }
        ],
        [
            {
                "Player ID": player_id,
                "Value": five_week_xpts / price,
                "Risk": float(player_id * 15),
                "Optimization Score": score,
            }
        ],
    )[0]
