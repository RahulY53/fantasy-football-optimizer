"""Tests for component-level statistical FPL scoring."""

from __future__ import annotations

import pytest

from fpl_optimizer.domain.enums import Position
from fpl_optimizer.domain.forecasts import ExpectedMinutes, PlayerForecastInput
from fpl_optimizer.forecasting.statistical import (
    expected_goals_conceded_deduction,
    project_statistical_xpts,
)


def test_midfielder_projection_sums_components() -> None:
    player = PlayerForecastInput(
        player_id=1,
        fpl_id=1,
        team_id=1,
        position=Position.MIDFIELDER,
        web_name="Mid",
        status="a",
        chance_next_round=None,
        minutes=900,
        starts=10,
        goals=4,
        assists=3,
        saves=0,
        bonus=5,
        price_tenths=80,
    )
    minutes = ExpectedMinutes(72, 0.85, 0.05, 0.9, 0.8, 80, 18, 1.0, "Medium")

    components, events = project_statistical_xpts(player, minutes, 1.1, 0.3, 1.2)

    assert components.total == pytest.approx(
        components.appearance
        + components.goals
        + components.assists
        + components.clean_sheet
        + components.saves
        + components.bonus
        + components.deductions
    )
    assert components.clean_sheet == pytest.approx(0.8 * 0.3)
    assert events["expected_goals"] > 0


def test_goals_conceded_deduction_is_zero_at_zero_lambda() -> None:
    assert expected_goals_conceded_deduction(0) == 0
    assert expected_goals_conceded_deduction(2.0) > 0


def test_events_without_minutes_do_not_create_false_rates() -> None:
    player = PlayerForecastInput(
        player_id=1,
        fpl_id=1,
        team_id=1,
        position=Position.GOALKEEPER,
        web_name="Preseason placeholder",
        status="a",
        chance_next_round=None,
        minutes=0,
        starts=0,
        goals=11,
        assists=0,
        saves=0,
        bonus=0,
        price_tenths=50,
    )
    minutes = ExpectedMinutes(65, 0.7, 0.01, 0.71, 0.69, 90, 1, 1.0, "Low")

    _, events = project_statistical_xpts(player, minutes, 1.0, 0.3, 1.2)

    assert events["expected_goals"] < 0.01
