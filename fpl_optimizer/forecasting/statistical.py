"""Basic component-level statistical FPL points model."""

from __future__ import annotations

import math

from fpl_optimizer.domain.enums import Position
from fpl_optimizer.domain.forecasts import (
    ExpectedMinutes,
    PlayerForecastInput,
    StatisticalComponents,
)

GOAL_POINTS = {
    Position.GOALKEEPER: 6,
    Position.DEFENDER: 6,
    Position.MIDFIELDER: 5,
    Position.FORWARD: 4,
}
CLEAN_SHEET_POINTS = {
    Position.GOALKEEPER: 4,
    Position.DEFENDER: 4,
    Position.MIDFIELDER: 1,
    Position.FORWARD: 0,
}
GOAL_PRIOR_PER_90 = {
    Position.GOALKEEPER: 0.002,
    Position.DEFENDER: 0.055,
    Position.MIDFIELDER: 0.23,
    Position.FORWARD: 0.36,
}
ASSIST_PRIOR_PER_90 = {
    Position.GOALKEEPER: 0.005,
    Position.DEFENDER: 0.085,
    Position.MIDFIELDER: 0.18,
    Position.FORWARD: 0.13,
}
BONUS_PRIOR_PER_90 = {
    Position.GOALKEEPER: 0.12,
    Position.DEFENDER: 0.16,
    Position.MIDFIELDER: 0.20,
    Position.FORWARD: 0.18,
}
PRIOR_MINUTES = 900.0


def project_statistical_xpts(
    player: PlayerForecastInput,
    minutes: ExpectedMinutes,
    team_attack_multiplier: float,
    clean_sheet_probability: float,
    opponent_xg: float,
) -> tuple[StatisticalComponents, dict[str, float]]:
    """Project one fixture using probability-weighted official FPL scoring."""

    attacking_signal = advanced_attacking_multiplier(player)
    expected_goals = (
        shrunk_rate_per90(player.goals, player.minutes, GOAL_PRIOR_PER_90[player.position])
        * minutes.expected_minutes
        / 90.0
        * team_attack_multiplier
        * attacking_signal
    )
    expected_assists = (
        shrunk_rate_per90(player.assists, player.minutes, ASSIST_PRIOR_PER_90[player.position])
        * minutes.expected_minutes
        / 90.0
        * team_attack_multiplier
        * attacking_signal
    )
    p_under_60 = max(minutes.p_appearance - minutes.p_60_plus, 0.0)
    appearance_points = p_under_60 + 2.0 * minutes.p_60_plus
    goal_points = expected_goals * GOAL_POINTS[player.position]
    assist_points = expected_assists * 3.0
    clean_sheet_points = (
        minutes.p_60_plus * clean_sheet_probability * CLEAN_SHEET_POINTS[player.position]
    )
    save_points = _save_points(player, minutes)
    bonus_points = (
        shrunk_rate_per90(player.bonus, player.minutes, BONUS_PRIOR_PER_90[player.position])
        * minutes.expected_minutes
        / 90.0
        * bps_bonus_multiplier(player)
    )
    deduction_points = -0.05 * minutes.p_appearance
    if player.position in (Position.GOALKEEPER, Position.DEFENDER):
        deduction_points -= minutes.p_60_plus * expected_goals_conceded_deduction(opponent_xg)

    components = StatisticalComponents(
        appearance=appearance_points,
        goals=goal_points,
        assists=assist_points,
        clean_sheet=clean_sheet_points,
        saves=save_points,
        bonus=bonus_points,
        deductions=deduction_points,
    )
    events = {
        "expected_goals": expected_goals,
        "expected_assists": expected_assists,
        "clean_sheet_probability": clean_sheet_probability,
        "opponent_xg": opponent_xg,
        "team_attack_multiplier": team_attack_multiplier,
        "advanced_attacking_multiplier": attacking_signal,
        "bps_bonus_multiplier": bps_bonus_multiplier(player),
    }
    return components, events


def expected_goals_conceded_deduction(opponent_xg: float, max_goals: int = 12) -> float:
    """Return E[floor(goals conceded / 2)] for a Poisson goal count."""

    lam = max(opponent_xg, 0.0)
    return sum(
        (goals // 2) * math.exp(-lam) * lam**goals / math.factorial(goals)
        for goals in range(max_goals + 1)
    )


def _save_points(player: PlayerForecastInput, minutes: ExpectedMinutes) -> float:
    if player.position is not Position.GOALKEEPER:
        return 0.0
    save_rate = shrunk_rate_per90(player.saves, player.minutes, prior_rate=3.0)
    expected_saves = save_rate * minutes.expected_minutes / 90.0
    return expected_saves / 3.0


def shrunk_rate_per90(events: int, minutes: int, prior_rate: float) -> float:
    """Return an event rate shrunk toward a prior over 900 equivalent minutes."""

    observed_minutes = max(float(minutes), 0.0)
    validated_events = max(events, 0) if observed_minutes > 0 else 0
    prior_events = prior_rate * PRIOR_MINUTES / 90.0
    return (validated_events + prior_events) * 90.0 / (observed_minutes + PRIOR_MINUTES)


def advanced_attacking_multiplier(player: PlayerForecastInput) -> float:
    """Return a bounded ICT/form signal without overpowering event-rate evidence."""

    if player.minutes <= 0 or (player.ict_index <= 0 and player.points_per_game <= 0):
        return 1.0
    ict_per_90 = player.ict_index * 90.0 / player.minutes
    ict_signal = (ict_per_90 - 6.0) / 20.0
    form_signal = (player.form - player.points_per_game) / 10.0
    adjustment = _clip(0.75 * ict_signal + 0.25 * form_signal, -0.15, 0.15)
    return 1.0 + adjustment


def bps_bonus_multiplier(player: PlayerForecastInput) -> float:
    """Use BPS per 90 as a bounded supporting signal for future bonus."""

    if player.minutes <= 0 or player.bps <= 0:
        return 1.0
    bps_per_90 = player.bps * 90.0 / player.minutes
    return 1.0 + _clip((bps_per_90 - 18.0) / 100.0, -0.12, 0.12)


def _clip(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)
