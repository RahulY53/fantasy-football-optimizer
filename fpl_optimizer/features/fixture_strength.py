"""Basic explainable fixture attack and clean-sheet features."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from fpl_optimizer.domain.forecasts import TeamStrength

BASELINE_TEAM_XG = 1.35
FDR_ATTACK_MULTIPLIER = {1: 1.25, 2: 1.12, 3: 1.0, 4: 0.88, 5: 0.75}


@dataclass(frozen=True, slots=True)
class StrengthAverages:
    """League reference ratings for home/away comparisons."""

    attack_home: float
    attack_away: float
    defence_home: float
    defence_away: float


def league_strength_averages(teams: list[TeamStrength]) -> StrengthAverages:
    """Calculate positive-only means, returning zeros when ratings are unavailable."""

    return StrengthAverages(
        attack_home=_positive_mean(team.attack_home for team in teams),
        attack_away=_positive_mean(team.attack_away for team in teams),
        defence_home=_positive_mean(team.defence_home for team in teams),
        defence_away=_positive_mean(team.defence_away for team in teams),
    )


def attack_multiplier(
    attacking_team: TeamStrength,
    defending_team: TeamStrength,
    is_home: bool,
    difficulty: int,
    averages: StrengthAverages,
) -> float:
    """Return a bounded team attacking multiplier for a single fixture."""

    attack = attacking_team.attack_home if is_home else attacking_team.attack_away
    defence = defending_team.defence_away if is_home else defending_team.defence_home
    average_attack = averages.attack_home if is_home else averages.attack_away
    average_defence = averages.defence_away if is_home else averages.defence_home

    if min(attack, defence, average_attack, average_defence) <= 0:
        return FDR_ATTACK_MULTIPLIER.get(difficulty, 1.0)

    rating_multiplier = (attack / average_attack) * (average_defence / defence)
    fdr_multiplier = FDR_ATTACK_MULTIPLIER.get(difficulty, 1.0)
    return _clip(0.8 * rating_multiplier + 0.2 * fdr_multiplier, 0.65, 1.45)


def clean_sheet_probability(opponent_attack_multiplier: float) -> float:
    """Estimate clean-sheet probability from a Poisson opponent goal mean."""

    opponent_xg = BASELINE_TEAM_XG * _clip(opponent_attack_multiplier, 0.5, 1.6)
    return math.exp(-opponent_xg)


def opponent_expected_goals(opponent_attack_multiplier: float) -> float:
    """Return the baseline statistical opponent expected-goal estimate."""

    return BASELINE_TEAM_XG * _clip(opponent_attack_multiplier, 0.5, 1.6)


def _positive_mean(values: Iterable[int]) -> float:
    positive = [float(value) for value in values if value > 0]
    return sum(positive) / len(positive) if positive else 0.0


def _clip(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)
