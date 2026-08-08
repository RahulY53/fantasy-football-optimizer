"""Reproducible component-level current-team Monte Carlo simulation."""

from __future__ import annotations

from collections import Counter

import numpy as np

from fpl_optimizer.domain.enums import Position
from fpl_optimizer.domain.simulation import (
    HistogramBin,
    PlayerSimulationSummary,
    SimulationPlayerInput,
    SimulationResult,
    WeekSimulationSummary,
)
from fpl_optimizer.forecasting.statistical import CLEAN_SHEET_POINTS, GOAL_POINTS
from fpl_optimizer.optimizer.lineup import LEGAL_FORMATIONS
from fpl_optimizer.optimizer.squad import POSITION_LIMITS, SQUAD_SIZE

ATTACK_SHOCK_SIGMA = 0.25


def simulate_current_team(
    players: list[SimulationPlayerInput],
    *,
    iterations: int,
    seed: int,
) -> SimulationResult:
    """Simulate a fixed current squad with expected-optimal weekly decisions."""

    horizon = _validate(players, iterations, seed)
    rng = np.random.default_rng(seed)
    player_count = len(players)
    raw_player_totals = np.zeros((iterations, player_count))
    week_totals: list[np.ndarray] = []
    week_summaries: list[WeekSimulationSummary] = []
    selected_counts = Counter[int]()
    captain_counts = Counter[int]()

    for week_index in range(horizon):
        starter_indices, formation = _select_lineup(players, week_index)
        captain_index = max(
            starter_indices,
            key=lambda index: (
                players[index].weeks[week_index].total_xpts,
                -players[index].player_id,
            ),
        )
        simulated = _simulate_week(players, week_index, iterations, rng)
        for index in starter_indices:
            raw_player_totals[:, index] += simulated[:, index]
            selected_counts[index] += 1
        raw_player_totals[:, captain_index] += simulated[:, captain_index]
        captain_counts[captain_index] += 1
        totals = simulated[:, starter_indices].sum(axis=1) + simulated[:, captain_index]
        week_totals.append(totals)
        expected = sum(players[index].weeks[week_index].total_xpts for index in starter_indices)
        expected += players[captain_index].weeks[week_index].total_xpts
        source = players[0].weeks[week_index]
        week_summaries.append(
            WeekSimulationSummary(
                gameweek_id=source.gameweek_id,
                gameweek=source.gameweek,
                formation=formation,
                captain_id=players[captain_index].player_id,
                captain=players[captain_index].player,
                starter_ids=tuple(sorted(players[index].player_id for index in starter_indices)),
                expected_points=expected,
                mean=float(np.mean(totals)),
                median=float(np.median(totals)),
                p10=float(np.percentile(totals, 10)),
                p90=float(np.percentile(totals, 90)),
                probability_40_plus=float(np.mean(totals >= 40)),
            )
        )

    total = np.sum(np.column_stack(week_totals), axis=1)
    player_summaries = tuple(
        _player_summary(
            player,
            raw_player_totals[:, index],
            selected_counts[index],
            captain_counts[index],
        )
        for index, player in enumerate(players)
        if selected_counts[index] > 0
    )
    counts, edges = np.histogram(total, bins=min(24, max(10, iterations // 500)))
    histogram = tuple(
        HistogramBin(float(edges[index]), float(edges[index + 1]), int(count))
        for index, count in enumerate(counts)
    )
    return SimulationResult(
        iterations=iterations,
        seed=seed,
        horizon=horizon,
        mean=float(np.mean(total)),
        median=float(np.median(total)),
        standard_deviation=float(np.std(total)),
        p10=float(np.percentile(total, 10)),
        p25=float(np.percentile(total, 25)),
        p75=float(np.percentile(total, 75)),
        p90=float(np.percentile(total, 90)),
        probability_below_40_per_gw=float(np.mean(total < 40 * horizon)),
        probability_50_per_gw_plus=float(np.mean(total >= 50 * horizon)),
        probability_60_per_gw_plus=float(np.mean(total >= 60 * horizon)),
        weeks=tuple(week_summaries),
        players=player_summaries,
        histogram=histogram,
    )


def _simulate_week(
    players: list[SimulationPlayerInput],
    week_index: int,
    iterations: int,
    rng: np.random.Generator,
) -> np.ndarray:
    values = np.zeros((iterations, len(players)))
    teams = sorted({player.team for player in players})
    attack_shocks = {
        team: rng.lognormal(
            mean=-(ATTACK_SHOCK_SIGMA**2) / 2,
            sigma=ATTACK_SHOCK_SIGMA,
            size=iterations,
        )
        for team in teams
    }
    clean_sheet_draws = {team: rng.random(iterations) for team in teams}
    for index, player in enumerate(players):
        week = player.weeks[week_index]
        position = Position(player.position)
        appearance_draw = rng.random(iterations)
        appeared = appearance_draw < week.p_appearance
        reached_60 = appearance_draw < week.p_60_plus
        appearance_mean = week.p_appearance + week.p_60_plus
        appearance_scale = week.appearance_xpts / max(appearance_mean, 1e-6)
        appearance = (
            appeared.astype(float) + reached_60.astype(float)
        ) * appearance_scale
        conditional_appearance = max(week.p_appearance, 1e-6)
        goal_rate = week.goal_xpts / GOAL_POINTS[position] / conditional_appearance
        assist_rate = week.assist_xpts / 3.0 / conditional_appearance
        shock = attack_shocks[player.team]
        goals = rng.poisson(np.maximum(goal_rate * shock, 0.0)) * appeared
        assists = rng.poisson(np.maximum(assist_rate * shock, 0.0)) * appeared
        clean_points = CLEAN_SHEET_POINTS[position]
        clean_sheet: np.ndarray
        if clean_points > 0 and week.clean_sheet_xpts > 0:
            joint_probability = min(week.clean_sheet_xpts / clean_points, 1.0)
            clean_sheet = (
                clean_sheet_draws[player.team] < joint_probability
            ) * clean_points
        else:
            clean_sheet = np.zeros(iterations)
        saves = rng.poisson(max(week.save_xpts, 0.0), size=iterations)
        bonus = np.minimum(rng.poisson(max(week.bonus_xpts, 0.0), size=iterations), 3)
        defensive_contribution = (
            rng.random(iterations) < min(max(week.defensive_contribution_xpts / 2.0, 0.0), 1.0)
        ) * 2
        deductions = rng.poisson(max(-week.deduction_xpts, 0.0), size=iterations)
        values[:, index] = (
            appearance
            + goals * GOAL_POINTS[position]
            + assists * 3
            + clean_sheet
            + saves
            + bonus
            + defensive_contribution
            - deductions
        )
    return values


def _select_lineup(
    players: list[SimulationPlayerInput], week_index: int
) -> tuple[list[int], str]:
    by_position = {
        position: sorted(
            (index for index, player in enumerate(players) if player.position == position),
            key=lambda index: (
                players[index].weeks[week_index].total_xpts,
                -players[index].player_id,
            ),
            reverse=True,
        )
        for position in POSITION_LIMITS
    }
    best: tuple[float, list[int], str] | None = None
    for defenders, midfielders, forwards in LEGAL_FORMATIONS:
        indices = (
            by_position["GK"][:1]
            + by_position["DEF"][:defenders]
            + by_position["MID"][:midfielders]
            + by_position["FWD"][:forwards]
        )
        score = sum(players[index].weeks[week_index].total_xpts for index in indices)
        formation = f"{defenders}-{midfielders}-{forwards}"
        candidate = (score, indices, formation)
        if best is None or (score, formation) > (best[0], best[2]):
            best = candidate
    if best is None:
        raise RuntimeError("No legal simulated lineup is available")
    return best[1], best[2]


def _player_summary(
    player: SimulationPlayerInput,
    values: np.ndarray,
    selected_gameweeks: int,
    captained_gameweeks: int,
) -> PlayerSimulationSummary:
    return PlayerSimulationSummary(
        player_id=player.player_id,
        player=player.player,
        position=player.position,
        team=player.team,
        selected_gameweeks=selected_gameweeks,
        captained_gameweeks=captained_gameweeks,
        mean=float(np.mean(values)),
        median=float(np.median(values)),
        p10=float(np.percentile(values, 10)),
        p90=float(np.percentile(values, 90)),
        blank_probability=float(np.mean(values <= 2)),
        return_probability=float(np.mean(values >= 5)),
        haul_probability=float(np.mean(values >= 10)),
    )


def _validate(players: list[SimulationPlayerInput], iterations: int, seed: int) -> int:
    if not 1_000 <= iterations <= 50_000:
        raise ValueError("Simulation iterations must be between 1,000 and 50,000")
    if seed < 0:
        raise ValueError("Simulation seed cannot be negative")
    if len(players) != SQUAD_SIZE or len({player.player_id for player in players}) != SQUAD_SIZE:
        raise ValueError("Simulation requires exactly 15 unique current players")
    if Counter(player.position for player in players) != Counter(POSITION_LIMITS):
        raise ValueError("Simulation squad has invalid positional quotas")
    horizon = len(players[0].weeks)
    if not 1 <= horizon <= 6:
        raise ValueError("Simulation horizon must be between one and six Gameweeks")
    if any(len(player.weeks) != horizon for player in players):
        raise ValueError("Simulation inputs must share one aligned horizon")
    return horizon
