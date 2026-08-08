"""Tests for component-level statistical FPL scoring."""

from __future__ import annotations

import pytest

from fpl_optimizer.domain.enums import Position
from fpl_optimizer.domain.forecasts import ExpectedMinutes, PlayerForecastInput
from fpl_optimizer.forecasting.statistical import (
    GOAL_POINTS,
    expected_goals_conceded_deduction,
    expected_threshold_units,
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
        + components.defensive_contribution
    )
    assert components.clean_sheet == pytest.approx(0.8 * 0.3)
    assert events["expected_goals"] > 0


def test_2026_goal_values_and_threshold_scoring() -> None:
    assert GOAL_POINTS[Position.GOALKEEPER] == 10
    assert GOAL_POINTS[Position.DEFENDER] == 6
    assert GOAL_POINTS[Position.MIDFIELDER] == 5
    assert GOAL_POINTS[Position.FORWARD] == 4
    assert 0 < expected_threshold_units(2.0, 3) < 2.0 / 3.0


def test_defensive_contributions_and_event_deductions_are_projected() -> None:
    player = PlayerForecastInput(
        player_id=2,
        fpl_id=2,
        team_id=1,
        position=Position.DEFENDER,
        web_name="Centre-back",
        status="a",
        chance_next_round=None,
        minutes=900,
        starts=10,
        goals=0,
        assists=0,
        saves=0,
        bonus=0,
        price_tenths=50,
        defensive_contribution=120,
        yellow_cards=5,
        own_goals=1,
    )
    minutes = ExpectedMinutes(90, 1.0, 0.0, 1.0, 1.0, 90, 0, 1.0, "High")

    components, events = project_statistical_xpts(player, minutes, 1.0, 0.3, 0.0)

    assert 0 < components.defensive_contribution <= 2
    assert components.deductions < 0
    assert events["card_deductions"] < 0
    assert events["own_goal_deductions"] < 0


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
