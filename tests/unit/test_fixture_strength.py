"""Tests for fixture multipliers and clean-sheet probabilities."""

from __future__ import annotations

import math

import pytest

from fpl_optimizer.domain.forecasts import TeamStrength
from fpl_optimizer.features.fixture_strength import (
    attack_multiplier,
    clean_sheet_probability,
    league_strength_averages,
)


def team(team_id: int, rating: int) -> TeamStrength:
    return TeamStrength(team_id, f"Team {team_id}", f"T{team_id}", rating, rating, rating, rating)


def test_strength_rating_rewards_stronger_attack() -> None:
    strong = team(1, 1300)
    weak = team(2, 900)
    average = team(3, 1100)
    averages = league_strength_averages([strong, weak, average])

    strong_multiplier = attack_multiplier(strong, weak, True, 2, averages)
    weak_multiplier = attack_multiplier(weak, strong, False, 4, averages)

    assert strong_multiplier > 1
    assert weak_multiplier < 1


def test_fdr_is_fallback_when_ratings_are_missing() -> None:
    unknown_a = team(1, 0)
    unknown_b = team(2, 0)
    averages = league_strength_averages([unknown_a, unknown_b])

    assert attack_multiplier(unknown_a, unknown_b, True, 1, averages) == 1.25
    assert attack_multiplier(unknown_a, unknown_b, True, 5, averages) == 0.75


def test_clean_sheet_probability_uses_poisson_zero_goals() -> None:
    assert clean_sheet_probability(1.0) == pytest.approx(math.exp(-1.35))
