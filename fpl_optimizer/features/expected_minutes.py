"""Probability-weighted expected-minutes model with empirical role signals."""

from __future__ import annotations

from fpl_optimizer.domain.enums import Position
from fpl_optimizer.domain.forecasts import ExpectedMinutes, PlayerForecastInput

PRIOR_MATCHES = 3.0
SUB_APPEARANCE_RATE = {
    Position.GOALKEEPER: 0.03,
    Position.DEFENDER: 0.42,
    Position.MIDFIELDER: 0.48,
    Position.FORWARD: 0.48,
}
MINUTES_IF_START = {
    Position.GOALKEEPER: 90.0,
    Position.DEFENDER: 79.0,
    Position.MIDFIELDER: 76.0,
    Position.FORWARD: 75.0,
}
PRICE_BANDS = {
    Position.GOALKEEPER: (40, 60, 0.50, 0.92),
    Position.DEFENDER: (40, 75, 0.42, 0.90),
    Position.MIDFIELDER: (45, 130, 0.36, 0.92),
    Position.FORWARD: (45, 145, 0.42, 0.93),
}


def project_expected_minutes(
    player: PlayerForecastInput,
    team_matches_played: int,
) -> ExpectedMinutes:
    """Estimate transparent start/sub scenarios from season usage and priors.

    Price is used only as a weak preseason role prior when no lineup history exists.
    As matches accumulate, observed start rate and start duration replace that prior.
    """

    position = player.position
    prior_start = _price_role_prior(position, player.price_tenths)
    matches = max(team_matches_played, 0)
    default_start_minutes = MINUTES_IF_START[position]
    empirical_starts = min(max(player.starts, 0), matches) if matches else 0
    observed_start_rate = empirical_starts / matches if matches else prior_start
    minutes_role_rate = (
        _clip(player.minutes / max(matches * default_start_minutes, 1.0), 0.0, 1.0)
        if matches
        else prior_start
    )
    empirical_role = 0.7 * observed_start_rate + 0.3 * minutes_role_rate
    p_start_role = (matches * empirical_role + PRIOR_MATCHES * prior_start) / (
        matches + PRIOR_MATCHES
    )

    if player.starts > 0:
        observed_start_minutes = min(
            90.0,
            max(60.0, player.minutes / max(player.starts, 1)),
        )
        evidence_weight = min(player.starts / 6.0, 1.0)
        minutes_if_start = (
            evidence_weight * observed_start_minutes
            + (1.0 - evidence_weight) * default_start_minutes
        )
    else:
        minutes_if_start = default_start_minutes

    availability = availability_probability(player.status, player.chance_next_round)
    p_start = availability * _clip(p_start_role, 0.0, 1.0)
    minutes_if_sub = 1.0 if position is Position.GOALKEEPER else 18.0
    non_start_matches = max(matches - empirical_starts, 0)
    estimated_start_minutes = min(player.minutes, empirical_starts * minutes_if_start)
    residual_minutes = max(player.minutes - estimated_start_minutes, 0.0)
    observed_sub_rate = (
        _clip(residual_minutes / max(non_start_matches * minutes_if_sub, 1.0), 0.0, 1.0)
        if non_start_matches
        else SUB_APPEARANCE_RATE[position]
    )
    sub_evidence = min(non_start_matches / 6.0, 1.0)
    sub_rate = (
        sub_evidence * observed_sub_rate
        + (1.0 - sub_evidence) * SUB_APPEARANCE_RATE[position]
    )
    p_sub = availability * (1.0 - p_start_role) * sub_rate
    p_appearance = _clip(p_start + p_sub, 0.0, 1.0)
    reach_60_if_start = _clip((minutes_if_start - 45.0) / 30.0, 0.65, 0.99)
    p_60_plus = p_start * reach_60_if_start
    expected = p_start * minutes_if_start + p_sub * minutes_if_sub

    confidence = _confidence(matches, player.chance_next_round)
    return ExpectedMinutes(
        expected_minutes=_clip(expected, 0.0, 90.0),
        p_start=p_start,
        p_sub_appearance=p_sub,
        p_appearance=p_appearance,
        p_60_plus=p_60_plus,
        minutes_if_start=minutes_if_start,
        minutes_if_sub=minutes_if_sub,
        availability=availability,
        confidence=confidence,
    )


def availability_probability(status: str, chance_next_round: int | None) -> float:
    """Convert official availability fields into a bounded appearance cap."""

    if chance_next_round is not None:
        return _clip(chance_next_round / 100.0, 0.0, 1.0)
    if status == "a":
        return 1.0
    if status == "d":
        return 0.75
    return 0.0


def _price_role_prior(position: Position, price_tenths: int) -> float:
    low_price, high_price, low_probability, high_probability = PRICE_BANDS[position]
    share = _clip((price_tenths - low_price) / (high_price - low_price), 0.0, 1.0)
    return low_probability + share * (high_probability - low_probability)


def _confidence(matches: int, chance_next_round: int | None) -> str:
    if matches < 5 or chance_next_round not in (None, 0, 100):
        return "Low"
    if matches < 12:
        return "Medium"
    return "High"


def _clip(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)
