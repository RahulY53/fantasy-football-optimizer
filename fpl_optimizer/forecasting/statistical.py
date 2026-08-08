"""2026/27 component-level statistical FPL points model."""

from __future__ import annotations

import math

from fpl_optimizer.domain.enums import Position
from fpl_optimizer.domain.forecasts import (
    ExpectedMinutes,
    PlayerForecastInput,
    StatisticalComponents,
)

GOAL_POINTS = {
    Position.GOALKEEPER: 10,
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
DEFENSIVE_CONTRIBUTION_PRIOR_PER_90 = {
    Position.GOALKEEPER: 0.0,
    Position.DEFENDER: 9.0,
    Position.MIDFIELDER: 8.0,
    Position.FORWARD: 4.0,
}
YELLOW_CARD_PRIOR_PER_90 = 0.12
RED_CARD_PRIOR_PER_90 = 0.004
OWN_GOAL_PRIOR_PER_90 = 0.003
PENALTY_MISS_PRIOR_PER_90 = 0.006
PENALTY_SAVE_PRIOR_PER_90 = 0.015
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
    save_points = _save_points(player, minutes) + _penalty_save_points(player, minutes)
    defensive_contribution_points = _defensive_contribution_points(player, minutes)
    bonus_points = (
        shrunk_rate_per90(player.bonus, player.minutes, BONUS_PRIOR_PER_90[player.position])
        * minutes.expected_minutes
        / 90.0
        * bps_bonus_multiplier(player)
    )
    yellow_points = _rate_points(
        player.yellow_cards, player, minutes, YELLOW_CARD_PRIOR_PER_90, -1.0
    )
    red_points = _rate_points(player.red_cards, player, minutes, RED_CARD_PRIOR_PER_90, -3.0)
    own_goal_points = _rate_points(
        player.own_goals, player, minutes, OWN_GOAL_PRIOR_PER_90, -2.0
    )
    penalty_miss_points = _rate_points(
        player.penalties_missed, player, minutes, PENALTY_MISS_PRIOR_PER_90, -2.0
    )
    goals_conceded_points = 0.0
    if player.position in (Position.GOALKEEPER, Position.DEFENDER):
        goals_conceded_points = -(
            minutes.p_start
            * expected_goals_conceded_deduction(
                opponent_xg * minutes.minutes_if_start / 90.0
            )
            + minutes.p_sub_appearance
            * expected_goals_conceded_deduction(
                opponent_xg * minutes.minutes_if_sub / 90.0
            )
        )
    deduction_points = (
        yellow_points
        + red_points
        + own_goal_points
        + penalty_miss_points
        + goals_conceded_points
    )

    components = StatisticalComponents(
        appearance=appearance_points,
        goals=goal_points,
        assists=assist_points,
        clean_sheet=clean_sheet_points,
        saves=save_points,
        bonus=bonus_points,
        deductions=deduction_points,
        defensive_contribution=defensive_contribution_points,
    )
    events = {
        "expected_goals": expected_goals,
        "expected_assists": expected_assists,
        "clean_sheet_probability": clean_sheet_probability,
        "opponent_xg": opponent_xg,
        "team_attack_multiplier": team_attack_multiplier,
        "advanced_attacking_multiplier": attacking_signal,
        "bps_bonus_multiplier": bps_bonus_multiplier(player),
        "defensive_contribution_points": defensive_contribution_points,
        "card_deductions": yellow_points + red_points,
        "own_goal_deductions": own_goal_points,
        "penalty_miss_deductions": penalty_miss_points,
        "goals_conceded_deductions": goals_conceded_points,
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
    return _scenario_threshold_points(save_rate, minutes, threshold=3, points=1.0)


def _penalty_save_points(player: PlayerForecastInput, minutes: ExpectedMinutes) -> float:
    if player.position is not Position.GOALKEEPER:
        return 0.0
    rate = shrunk_rate_per90(
        player.penalties_saved,
        player.minutes,
        prior_rate=PENALTY_SAVE_PRIOR_PER_90,
    )
    return rate * minutes.expected_minutes / 90.0 * 5.0


def _defensive_contribution_points(
    player: PlayerForecastInput, minutes: ExpectedMinutes
) -> float:
    if player.position is Position.GOALKEEPER:
        return 0.0
    observed = player.defensive_contribution or (
        player.clearances_blocks_interceptions
        + player.tackles
        + (player.recoveries if player.position in (Position.MIDFIELDER, Position.FORWARD) else 0)
    )
    rate = shrunk_rate_per90(
        observed,
        player.minutes,
        DEFENSIVE_CONTRIBUTION_PRIOR_PER_90[player.position],
    )
    threshold = 10 if player.position is Position.DEFENDER else 12
    return _scenario_threshold_points(rate, minutes, threshold=threshold, points=2.0, capped=True)


def _rate_points(
    events: int,
    player: PlayerForecastInput,
    minutes: ExpectedMinutes,
    prior_rate: float,
    points: float,
) -> float:
    rate = shrunk_rate_per90(events, player.minutes, prior_rate)
    return rate * minutes.expected_minutes / 90.0 * points


def _scenario_threshold_points(
    rate_per_90: float,
    minutes: ExpectedMinutes,
    *,
    threshold: int,
    points: float,
    capped: bool = False,
) -> float:
    def scenario(duration: float) -> float:
        lam = max(rate_per_90 * duration / 90.0, 0.0)
        if capped:
            return points * poisson_tail_probability(lam, threshold)
        return points * expected_threshold_units(lam, threshold)

    return (
        minutes.p_start * scenario(minutes.minutes_if_start)
        + minutes.p_sub_appearance * scenario(minutes.minutes_if_sub)
    )


def poisson_tail_probability(lam: float, threshold: int) -> float:
    """Return P(Poisson(lam) >= threshold)."""

    if threshold <= 0:
        return 1.0
    validated = max(lam, 0.0)
    return max(
        0.0,
        1.0
        - sum(
            math.exp(-validated) * validated**events / math.factorial(events)
            for events in range(threshold)
        ),
    )


def expected_threshold_units(lam: float, threshold: int, max_events: int = 60) -> float:
    """Return E[floor(Poisson(lam) / threshold)] for threshold scoring."""

    if threshold <= 0:
        raise ValueError("Threshold must be positive")
    validated = max(lam, 0.0)
    return sum(
        (events // threshold)
        * math.exp(-validated)
        * validated**events
        / math.factorial(events)
        for events in range(max_events + 1)
    )


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
