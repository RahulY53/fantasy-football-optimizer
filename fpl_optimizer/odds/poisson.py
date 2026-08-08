"""Independent-Poisson match probabilities."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MatchProbabilities:
    """MVP outcomes implied by two Poisson goal means."""

    home_win: float
    draw: float
    away_win: float
    over_2_5: float
    tail_mass: float


def match_probabilities(home_xg: float, away_xg: float) -> MatchProbabilities:
    """Calculate match outcomes on an adaptive score grid."""

    if home_xg <= 0 or away_xg <= 0:
        raise ValueError("Expected goals must be positive")
    max_goals = 8
    while max_goals < 20:
        home_mass = sum(_poisson(home_xg, goals) for goals in range(max_goals + 1))
        away_mass = sum(_poisson(away_xg, goals) for goals in range(max_goals + 1))
        if 1.0 - home_mass * away_mass < 1e-8:
            break
        max_goals += 2

    home_win = draw = away_win = over = 0.0
    included_mass = 0.0
    for home_goals in range(max_goals + 1):
        for away_goals in range(max_goals + 1):
            probability = _poisson(home_xg, home_goals) * _poisson(away_xg, away_goals)
            included_mass += probability
            if home_goals > away_goals:
                home_win += probability
            elif home_goals == away_goals:
                draw += probability
            else:
                away_win += probability
            if home_goals + away_goals > 2:
                over += probability
    outcome_mass = home_win + draw + away_win
    return MatchProbabilities(
        home_win=home_win / outcome_mass,
        draw=draw / outcome_mass,
        away_win=away_win / outcome_mass,
        over_2_5=over / included_mass,
        tail_mass=max(0.0, 1.0 - included_mass),
    )


def _poisson(rate: float, goals: int) -> float:
    return math.exp(-rate) * rate**goals / math.factorial(goals)
