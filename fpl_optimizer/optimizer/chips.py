"""Exact Wildcard, Free Hit, Bench Boost, and Triple Captain evaluation."""

from __future__ import annotations

from collections import Counter

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp  # type: ignore[import-untyped]
from scipy.sparse import coo_array  # type: ignore[import-untyped]

from fpl_optimizer.domain.chips import (
    ChipCandidate,
    ChipEvaluation,
    ChipOpportunity,
    ChipWeekPlan,
)
from fpl_optimizer.optimizer.lineup import LEGAL_FORMATIONS
from fpl_optimizer.optimizer.squad import MAX_PER_TEAM, POSITION_LIMITS, SQUAD_SIZE


def evaluate_chips(
    candidates: list[ChipCandidate],
    *,
    current_ids: set[int],
    budget: float,
    gameweeks: list[tuple[int, str]],
    availability: dict[str, bool],
) -> ChipEvaluation:
    """Evaluate the best independent use of every supported chip."""

    current = _validate(candidates, current_ids, budget, gameweeks)
    names = {player.player_id: player.player for player in candidates}
    baseline = tuple(
        _current_week_plan(current, week_index, gameweek)
        for week_index, gameweek in enumerate(gameweeks)
    )
    baseline_total = sum(week.projected_points for week in baseline)

    wildcard_weeks = _optimize_squad(candidates, range(len(gameweeks)), budget, gameweeks)
    wildcard_ids = set(wildcard_weeks[0].squad_ids)
    wildcard_gain = sum(week.projected_points for week in wildcard_weeks) - baseline_total
    wildcard = ChipOpportunity(
        chip="Wildcard",
        available=availability.get("Wildcard", False),
        recommended_gameweek=gameweeks[0][1],
        projected_gain=wildcard_gain,
        rationale=(
            f"Rebuild the permanent squad for {wildcard_gain:.1f} additional projected points "
            f"over {len(gameweeks)} Gameweeks. Saved free transfers are preserved."
        ),
        players_in=tuple(sorted(wildcard_ids - current_ids)),
        players_out=tuple(sorted(current_ids - wildcard_ids)),
        weeks=wildcard_weeks,
    )

    free_hit_options: list[tuple[float, ChipWeekPlan]] = []
    for week_index, gameweek in enumerate(gameweeks):
        optimized = _optimize_squad(candidates, [week_index], budget, [gameweek])[0]
        gain = optimized.projected_points - baseline[week_index].projected_points
        free_hit_options.append((gain, optimized))
    free_hit_gain, free_hit_week = max(
        free_hit_options, key=lambda value: (value[0], -value[1].gameweek_id)
    )
    free_hit_ids = set(free_hit_week.squad_ids)
    free_hit = ChipOpportunity(
        chip="Free Hit",
        available=availability.get("Free Hit", False),
        recommended_gameweek=free_hit_week.gameweek,
        projected_gain=free_hit_gain,
        rationale=(
            f"Use a one-Gameweek squad in {free_hit_week.gameweek} for "
            f"{free_hit_gain:.1f} additional projected points, then restore the current squad."
        ),
        players_in=tuple(sorted(free_hit_ids - current_ids)),
        players_out=tuple(sorted(current_ids - free_hit_ids)),
        weeks=(free_hit_week,),
    )

    bench_options: list[tuple[float, ChipWeekPlan]] = []
    triple_options: list[tuple[float, ChipWeekPlan]] = []
    for week_index, week in enumerate(baseline):
        squad_xpts = sum(player.gameweek_xpts[week_index] for player in current)
        captain_xpts = next(
            player.gameweek_xpts[week_index]
            for player in current
            if player.player_id == week.captain_id
        )
        normal_lineup = week.projected_points - captain_xpts
        bench_options.append((squad_xpts - normal_lineup, week))
        triple_options.append((captain_xpts, week))
    bench_gain, bench_week = max(
        bench_options, key=lambda value: (value[0], -value[1].gameweek_id)
    )
    bench_boost = ChipOpportunity(
        chip="Bench Boost",
        available=availability.get("Bench Boost", False),
        recommended_gameweek=bench_week.gameweek,
        projected_gain=bench_gain,
        rationale=(
            f"Count all four bench players in {bench_week.gameweek} for "
            f"{bench_gain:.1f} additional projected points."
        ),
        players_in=(),
        players_out=(),
        weeks=(bench_week,),
    )
    triple_gain, triple_week = max(
        triple_options, key=lambda value: (value[0], -value[1].gameweek_id)
    )
    triple_captain = ChipOpportunity(
        chip="Triple Captain",
        available=availability.get("Triple Captain", False),
        recommended_gameweek=triple_week.gameweek,
        projected_gain=triple_gain,
        rationale=(
            f"Triple-captain {names[triple_week.captain_id]} in {triple_week.gameweek} for "
            f"{triple_gain:.1f} points above normal captaincy."
        ),
        players_in=(),
        players_out=(),
        weeks=(triple_week,),
    )
    opportunities = (wildcard, free_hit, bench_boost, triple_captain)
    usable = [opportunity for opportunity in opportunities if opportunity.available]
    best = max(usable, key=lambda item: (item.projected_gain, item.chip)) if usable else None
    return ChipEvaluation(
        horizon=len(gameweeks),
        budget=budget,
        current_projected_points=baseline_total,
        best_chip=best.chip if best else None,
        best_gain=best.projected_gain if best else 0.0,
        opportunities=opportunities,
    )


def _optimize_squad(
    candidates: list[ChipCandidate],
    week_indices: range | list[int],
    budget: float,
    gameweeks: list[tuple[int, str]],
) -> tuple[ChipWeekPlan, ...]:
    selected_weeks = list(week_indices)
    count = len(candidates)
    horizon = len(selected_weeks)
    squad_offset = 0
    starter_offset = count
    captain_offset = count + count * horizon
    variable_count = count + 2 * count * horizon

    def starter(player: int, week: int) -> int:
        return starter_offset + week * count + player

    def captain(player: int, week: int) -> int:
        return captain_offset + week * count + player

    objective = np.zeros(variable_count)
    for player_index, player in enumerate(candidates):
        objective[squad_offset + player_index] = (
            -1e-7 * player.optimization_score - 1e-11 * (count - player_index)
        )
        for local_week, source_week in enumerate(selected_weeks):
            xpts = player.gameweek_xpts[source_week]
            objective[starter(player_index, local_week)] = -xpts
            objective[captain(player_index, local_week)] = -xpts

    rows: list[dict[int, float]] = []
    lower: list[float] = []
    upper: list[float] = []

    def add(values: dict[int, float], minimum: float, maximum: float) -> None:
        rows.append(values)
        lower.append(minimum)
        upper.append(maximum)

    add({squad_offset + player: 1.0 for player in range(count)}, 15, 15)
    add(
        {squad_offset + player: candidates[player].price for player in range(count)},
        0,
        budget,
    )
    for position, required in POSITION_LIMITS.items():
        add(
            {
                squad_offset + index: 1.0
                for index, player in enumerate(candidates)
                if player.position == position
            },
            required,
            required,
        )
    for team in sorted({player.team for player in candidates}):
        add(
            {
                squad_offset + index: 1.0
                for index, player in enumerate(candidates)
                if player.team == team
            },
            0,
            MAX_PER_TEAM,
        )
    for week in range(horizon):
        add({starter(player, week): 1.0 for player in range(count)}, 11, 11)
        add({captain(player, week): 1.0 for player in range(count)}, 1, 1)
        for position, minimum, maximum in (
            ("GK", 1, 1),
            ("DEF", 3, 5),
            ("MID", 2, 5),
            ("FWD", 1, 3),
        ):
            add(
                {
                    starter(index, week): 1.0
                    for index, player in enumerate(candidates)
                    if player.position == position
                },
                minimum,
                maximum,
            )
        for player_index in range(count):
            add(
                {
                    starter(player_index, week): 1.0,
                    squad_offset + player_index: -1.0,
                },
                -np.inf,
                0,
            )
            add(
                {
                    captain(player_index, week): 1.0,
                    starter(player_index, week): -1.0,
                },
                -np.inf,
                0,
            )

    row_ids: list[int] = []
    column_ids: list[int] = []
    coefficients: list[float] = []
    for row_id, values in enumerate(rows):
        for column_id, coefficient in values.items():
            row_ids.append(row_id)
            column_ids.append(column_id)
            coefficients.append(coefficient)
    matrix = coo_array(
        (coefficients, (row_ids, column_ids)), shape=(len(rows), variable_count)
    ).tocsr()
    solved = milp(
        c=objective,
        integrality=np.ones(variable_count),
        bounds=Bounds(0.0, 1.0),
        constraints=LinearConstraint(matrix, lower, upper),
        options={"time_limit": 20.0, "mip_rel_gap": 0.0},
    )
    if not solved.success or solved.x is None:
        raise RuntimeError(f"No legal chip squad was found: {solved.message}")
    squad = [index for index in range(count) if solved.x[squad_offset + index] > 0.5]
    weeks: list[ChipWeekPlan] = []
    for local_week, source_week in enumerate(selected_weeks):
        starters = [
            index for index in range(count) if solved.x[starter(index, local_week)] > 0.5
        ]
        captain_index = next(
            index for index in range(count) if solved.x[captain(index, local_week)] > 0.5
        )
        positions = Counter(candidates[index].position for index in starters)
        projected = sum(candidates[index].gameweek_xpts[source_week] for index in starters)
        projected += candidates[captain_index].gameweek_xpts[source_week]
        gameweek_id, gameweek_name = gameweeks[local_week]
        weeks.append(
            ChipWeekPlan(
                gameweek_id=gameweek_id,
                gameweek=gameweek_name,
                squad_ids=tuple(sorted(candidates[index].player_id for index in squad)),
                starter_ids=tuple(sorted(candidates[index].player_id for index in starters)),
                captain_id=candidates[captain_index].player_id,
                captain=candidates[captain_index].player,
                formation=f"{positions['DEF']}-{positions['MID']}-{positions['FWD']}",
                projected_points=projected,
            )
        )
    return tuple(weeks)


def _current_week_plan(
    current: list[ChipCandidate], week_index: int, gameweek: tuple[int, str]
) -> ChipWeekPlan:
    by_position = {
        position: sorted(
            (player for player in current if player.position == position),
            key=lambda player: (player.gameweek_xpts[week_index], -player.player_id),
            reverse=True,
        )
        for position in POSITION_LIMITS
    }
    best: tuple[float, list[ChipCandidate], str] | None = None
    for defenders, midfielders, forwards in LEGAL_FORMATIONS:
        starters = (
            by_position["GK"][:1]
            + by_position["DEF"][:defenders]
            + by_position["MID"][:midfielders]
            + by_position["FWD"][:forwards]
        )
        points = sum(player.gameweek_xpts[week_index] for player in starters)
        formation = f"{defenders}-{midfielders}-{forwards}"
        if best is None or (points, formation) > (best[0], best[2]):
            best = (points, starters, formation)
    if best is None:
        raise RuntimeError("No legal current-team lineup is available")
    base, starters, formation = best
    captain = max(
        starters,
        key=lambda player: (player.gameweek_xpts[week_index], -player.player_id),
    )
    return ChipWeekPlan(
        gameweek_id=gameweek[0],
        gameweek=gameweek[1],
        squad_ids=tuple(sorted(player.player_id for player in current)),
        starter_ids=tuple(sorted(player.player_id for player in starters)),
        captain_id=captain.player_id,
        captain=captain.player,
        formation=formation,
        projected_points=base + captain.gameweek_xpts[week_index],
    )


def _validate(
    candidates: list[ChipCandidate],
    current_ids: set[int],
    budget: float,
    gameweeks: list[tuple[int, str]],
) -> list[ChipCandidate]:
    if not 1 <= len(gameweeks) <= 6:
        raise ValueError("Chip horizon must be between one and six Gameweeks")
    if budget <= 0:
        raise ValueError("Chip budget must be positive")
    if len(current_ids) != SQUAD_SIZE:
        raise ValueError("Chip evaluation requires exactly 15 current players")
    if len({player.player_id for player in candidates}) != len(candidates):
        raise ValueError("Chip candidate IDs must be unique")
    current = [player for player in candidates if player.player_id in current_ids]
    if len(current) != SQUAD_SIZE:
        raise ValueError("Every current player requires a chip forecast")
    if Counter(player.position for player in current) != Counter(POSITION_LIMITS):
        raise ValueError("Current squad has invalid positional quotas")
    if any(len(player.gameweek_xpts) != len(gameweeks) for player in candidates):
        raise ValueError("Every chip candidate requires aligned Gameweek forecasts")
    return current
