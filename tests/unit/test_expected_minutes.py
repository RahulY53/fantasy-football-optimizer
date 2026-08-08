"""Tests for the explainable expected-minutes model."""

from __future__ import annotations

import pytest

from fpl_optimizer.domain.enums import Position
from fpl_optimizer.domain.forecasts import PlayerForecastInput
from fpl_optimizer.features.expected_minutes import (
    availability_probability,
    project_expected_minutes,
)


def player(**overrides: object) -> PlayerForecastInput:
    values: dict[str, object] = {
        "player_id": 1,
        "fpl_id": 101,
        "team_id": 1,
        "position": Position.MIDFIELDER,
        "web_name": "Example",
        "status": "a",
        "chance_next_round": None,
        "minutes": 720,
        "starts": 8,
        "goals": 2,
        "assists": 2,
        "saves": 0,
        "bonus": 3,
        "price_tenths": 80,
    }
    values.update(overrides)
    return PlayerForecastInput(**values)  # type: ignore[arg-type]


def test_expected_minutes_are_scenario_weighted() -> None:
    result = project_expected_minutes(player(), team_matches_played=10)

    expected = result.p_start * result.minutes_if_start + (
        result.p_sub_appearance * result.minutes_if_sub
    )
    assert result.expected_minutes == pytest.approx(expected)
    assert 0 <= result.p_60_plus <= result.p_start <= result.p_appearance <= 1
    assert result.confidence == "Medium"


def test_unavailable_player_projects_zero_minutes() -> None:
    result = project_expected_minutes(
        player(status="i", chance_next_round=0), team_matches_played=10
    )

    assert result.expected_minutes == 0
    assert result.p_appearance == 0


def test_availability_uses_official_chance() -> None:
    assert availability_probability("d", 75) == 0.75
    assert availability_probability("a", None) == 1.0
    assert availability_probability("i", None) == 0.0


def test_minutes_share_separates_established_starter_from_squad_player() -> None:
    starter = project_expected_minutes(player(minutes=870, starts=10), team_matches_played=10)
    squad_player = project_expected_minutes(
        player(minutes=250, starts=2), team_matches_played=10
    )

    assert starter.p_start > squad_player.p_start
    assert starter.expected_minutes > squad_player.expected_minutes
