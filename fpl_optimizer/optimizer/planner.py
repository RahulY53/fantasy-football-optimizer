"""Joint multi-Gameweek transfer, squad, lineup, and captain optimization."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp  # type: ignore[import-untyped]
from scipy.sparse import coo_array  # type: ignore[import-untyped]

from fpl_optimizer.domain.planner import (
    MultiGameweekPlan,
    PlannedGameweek,
    PlannedTransfer,
    PlanningCandidate,
)
from fpl_optimizer.optimizer.squad import MAX_PER_TEAM, POSITION_LIMITS, SQUAD_SIZE

MAX_FREE_TRANSFERS = 5
MAX_TRANSFERS_PER_WEEK = 2
TRANSFER_HIT = 4


def optimize_multi_gameweek(
    candidates: list[PlanningCandidate],
    *,
    gameweeks: list[tuple[int, str]],
    bank: float,
    free_transfers: int,
) -> MultiGameweekPlan:
    """Solve one exact plan across every supplied Gameweek."""

    _validate(candidates, gameweeks, bank, free_transfers)
    player_count = len(candidates)
    horizon = len(gameweeks)
    # Per player/week: squad, starter, captain, transfer in, transfer out.
    player_block = player_count * horizon
    squad_offset = 0
    starter_offset = player_block
    captain_offset = player_block * 2
    transfer_in_offset = player_block * 3
    transfer_out_offset = player_block * 4
    action_offset = player_block * 5
    action_count = horizon * (MAX_FREE_TRANSFERS + 1) * (MAX_TRANSFERS_PER_WEEK + 1)
    variable_count = action_offset + action_count

    def pv(offset: int, player: int, week: int) -> int:
        return offset + week * player_count + player

    def action(week: int, available: int, transfers: int) -> int:
        return (
            action_offset
            + week * (MAX_FREE_TRANSFERS + 1) * (MAX_TRANSFERS_PER_WEEK + 1)
            + available * (MAX_TRANSFERS_PER_WEEK + 1)
            + transfers
        )

    objective = np.zeros(variable_count)
    for week in range(horizon):
        for index, player in enumerate(candidates):
            xpts = player.gameweek_xpts[week]
            objective[pv(starter_offset, index, week)] = -xpts
            objective[pv(captain_offset, index, week)] = -xpts
            if week == horizon - 1:
                objective[pv(squad_offset, index, week)] = (
                    -1e-7 * player.optimization_score - 1e-11 * (player_count - index)
                )
            # If projected points are identical, preserve flexibility by delaying the move.
            objective[pv(transfer_in_offset, index, week)] = 1e-6 * (horizon - week)
        for available in range(MAX_FREE_TRANSFERS + 1):
            for transfers in range(MAX_TRANSFERS_PER_WEEK + 1):
                hits = max(0, transfers - available)
                objective[action(week, available, transfers)] = TRANSFER_HIT * hits

    rows: list[dict[int, float]] = []
    lower: list[float] = []
    upper: list[float] = []

    def add(coefficients: dict[int, float], minimum: float, maximum: float) -> None:
        rows.append(coefficients)
        lower.append(minimum)
        upper.append(maximum)

    current_ids = {player.player_id for player in candidates if player.is_current}
    for week in range(horizon):
        add({pv(squad_offset, p, week): 1.0 for p in range(player_count)}, 15, 15)
        add({pv(starter_offset, p, week): 1.0 for p in range(player_count)}, 11, 11)
        add({pv(captain_offset, p, week): 1.0 for p in range(player_count)}, 1, 1)
        for position, required in POSITION_LIMITS.items():
            squad_vars = {
                pv(squad_offset, p, week): 1.0
                for p, player in enumerate(candidates)
                if player.position == position
            }
            add(squad_vars, required, required)
        for position, minimum, maximum in (
            ("GK", 1, 1),
            ("DEF", 3, 5),
            ("MID", 2, 5),
            ("FWD", 1, 3),
        ):
            starter_vars = {
                pv(starter_offset, p, week): 1.0
                for p, player in enumerate(candidates)
                if player.position == position
            }
            add(starter_vars, minimum, maximum)
        for team in sorted({player.team for player in candidates}):
            add(
                {
                    pv(squad_offset, p, week): 1.0
                    for p, player in enumerate(candidates)
                    if player.team == team
                },
                0,
                MAX_PER_TEAM,
            )
        for p, player in enumerate(candidates):
            add(
                {
                    pv(starter_offset, p, week): 1.0,
                    pv(squad_offset, p, week): -1.0,
                },
                -np.inf,
                0,
            )
            add(
                {
                    pv(captain_offset, p, week): 1.0,
                    pv(starter_offset, p, week): -1.0,
                },
                -np.inf,
                0,
            )
            previous = 1.0 if player.player_id in current_ids else 0.0
            transition = {
                pv(squad_offset, p, week): 1.0,
                pv(transfer_in_offset, p, week): -1.0,
                pv(transfer_out_offset, p, week): 1.0,
            }
            if week == 0:
                add(transition, previous, previous)
            else:
                transition[pv(squad_offset, p, week - 1)] = -1.0
                add(transition, 0, 0)
            add(
                {
                    pv(transfer_in_offset, p, week): 1.0,
                    pv(transfer_out_offset, p, week): 1.0,
                },
                0,
                1,
            )
        transfer_count_vars = {
            pv(transfer_in_offset, p, week): 1.0 for p in range(player_count)
        }
        transfer_count_vars.update(
            {
                action(week, available, transfers): -float(transfers)
                for available in range(MAX_FREE_TRANSFERS + 1)
                for transfers in range(MAX_TRANSFERS_PER_WEEK + 1)
            }
        )
        add(transfer_count_vars, 0, 0)
        add(
            {pv(transfer_out_offset, p, week): 1.0 for p in range(player_count)},
            0,
            MAX_TRANSFERS_PER_WEEK,
        )
        add(
            {
                action(week, available, transfers): 1.0
                for available in range(MAX_FREE_TRANSFERS + 1)
                for transfers in range(MAX_TRANSFERS_PER_WEEK + 1)
            },
            1,
            1,
        )
        if week == 0:
            add(
                {
                    action(week, available, transfers): 1.0
                    for available in range(MAX_FREE_TRANSFERS + 1)
                    for transfers in range(MAX_TRANSFERS_PER_WEEK + 1)
                    if available == free_transfers
                },
                1,
                1,
            )
        else:
            for available in range(MAX_FREE_TRANSFERS + 1):
                incoming_state = {
                    action(week, available, transfers): 1.0
                    for transfers in range(MAX_TRANSFERS_PER_WEEK + 1)
                }
                for prior_available in range(MAX_FREE_TRANSFERS + 1):
                    for prior_transfers in range(MAX_TRANSFERS_PER_WEEK + 1):
                        next_available = min(
                            MAX_FREE_TRANSFERS,
                            max(0, prior_available - prior_transfers) + 1,
                        )
                        if next_available == available:
                            prior_action = action(week - 1, prior_available, prior_transfers)
                            incoming_state[prior_action] = -1.0
                add(incoming_state, 0, 0)
        budget_variables: dict[int, float] = {}
        for prior_week in range(week + 1):
            for p, player in enumerate(candidates):
                budget_variables[pv(transfer_in_offset, p, prior_week)] = player.buy_price
                budget_variables[pv(transfer_out_offset, p, prior_week)] = -player.selling_price
        add(budget_variables, -np.inf, bank)

    row_indices: list[int] = []
    column_indices: list[int] = []
    coefficients: list[float] = []
    for row_index, values in enumerate(rows):
        for variable, coefficient in values.items():
            row_indices.append(row_index)
            column_indices.append(variable)
            coefficients.append(coefficient)
    matrix = coo_array(
        (coefficients, (row_indices, column_indices)),
        shape=(len(rows), variable_count),
    ).tocsr()
    solved = milp(
        c=objective,
        integrality=np.ones(variable_count),
        bounds=Bounds(0.0, 1.0),
        constraints=LinearConstraint(matrix, lower, upper),
        options={"time_limit": 30.0, "mip_rel_gap": 0.0},
    )
    if not solved.success or solved.x is None:
        raise RuntimeError(f"No optimal multi-Gameweek plan was found: {solved.message}")
    return _build_result(
        solved.x,
        candidates=candidates,
        gameweeks=gameweeks,
        bank=bank,
        free_transfers=free_transfers,
        offsets=(
            squad_offset,
            starter_offset,
            captain_offset,
            transfer_in_offset,
            transfer_out_offset,
        ),
        action_index=action,
        player_index=pv,
    )


def _build_result(
    values: np.ndarray,
    *,
    candidates: list[PlanningCandidate],
    gameweeks: list[tuple[int, str]],
    bank: float,
    free_transfers: int,
    offsets: tuple[int, int, int, int, int],
    action_index: Callable[[int, int, int], int],
    player_index: Callable[[int, int, int], int],
) -> MultiGameweekPlan:
    # Callables are passed to keep index arithmetic in one place in the solver.
    action = action_index
    pv = player_index
    squad_offset, starter_offset, captain_offset, transfer_in_offset, transfer_out_offset = offsets
    running_bank = bank
    available = free_transfers
    weeks: list[PlannedGameweek] = []
    total_hits = 0
    for week, (gameweek_id, gameweek_name) in enumerate(gameweeks):
        squad = [p for p in range(len(candidates)) if values[pv(squad_offset, p, week)] > 0.5]
        starters = [
            p for p in range(len(candidates)) if values[pv(starter_offset, p, week)] > 0.5
        ]
        captain = next(
            p for p in range(len(candidates)) if values[pv(captain_offset, p, week)] > 0.5
        )
        incoming = [
            candidates[p]
            for p in range(len(candidates))
            if values[pv(transfer_in_offset, p, week)] > 0.5
        ]
        outgoing = [
            candidates[p]
            for p in range(len(candidates))
            if values[pv(transfer_out_offset, p, week)] > 0.5
        ]
        transfers = next(
            count
            for count in range(MAX_TRANSFERS_PER_WEEK + 1)
            if values[action(week, available, count)] > 0.5
        )
        moves = _pair_transfers(outgoing, incoming)
        hit = TRANSFER_HIT * max(0, transfers - available)
        total_hits += hit
        running_bank += sum(player.selling_price for player in outgoing) - sum(
            player.buy_price for player in incoming
        )
        positions = Counter(candidates[p].position for p in starters)
        lineup_xpts = sum(candidates[p].gameweek_xpts[week] for p in starters)
        captain_xpts = candidates[captain].gameweek_xpts[week]
        next_available = min(MAX_FREE_TRANSFERS, max(0, available - transfers) + 1)
        weeks.append(
            PlannedGameweek(
                gameweek_id=gameweek_id,
                gameweek=gameweek_name,
                transfers=moves,
                free_transfers_before=available,
                free_transfers_after=next_available,
                hit_cost=hit,
                bank_after=running_bank,
                formation=f"{positions['DEF']}-{positions['MID']}-{positions['FWD']}",
                captain_id=candidates[captain].player_id,
                captain=candidates[captain].player,
                starter_ids=tuple(sorted(candidates[p].player_id for p in starters)),
                squad_ids=tuple(sorted(candidates[p].player_id for p in squad)),
                lineup_xpts=lineup_xpts,
                captain_xpts=captain_xpts,
                projected_points=lineup_xpts + captain_xpts,
                net_projected_points=lineup_xpts + captain_xpts - hit,
            )
        )
        available = next_available
    gross = sum(week.projected_points for week in weeks)
    return MultiGameweekPlan(
        status="optimal",
        solver="scipy-highs-milp",
        horizon=len(gameweeks),
        starting_bank=bank,
        starting_free_transfers=free_transfers,
        total_transfers=sum(len(week.transfers) for week in weeks),
        total_hits=total_hits,
        gross_projected_points=gross,
        net_projected_points=gross - total_hits,
        weeks=tuple(weeks),
    )


def _pair_transfers(
    outgoing: list[PlanningCandidate], incoming: list[PlanningCandidate]
) -> tuple[PlannedTransfer, ...]:
    moves: list[PlannedTransfer] = []
    for position in POSITION_LIMITS:
        outs = sorted((p for p in outgoing if p.position == position), key=lambda p: p.player_id)
        ins = sorted((p for p in incoming if p.position == position), key=lambda p: p.player_id)
        if len(outs) != len(ins):
            raise RuntimeError("Planned transfers could not be paired by position")
        for sold, bought in zip(outs, ins, strict=True):
            moves.append(
                PlannedTransfer(
                    out_player_id=sold.player_id,
                    out_player=sold.player,
                    out_team=sold.team,
                    selling_price=sold.selling_price,
                    in_player_id=bought.player_id,
                    in_player=bought.player,
                    in_team=bought.team,
                    buy_price=bought.buy_price,
                    position=position,
                    bank_change=bought.buy_price - sold.selling_price,
                )
            )
    return tuple(moves)


def _validate(
    candidates: list[PlanningCandidate],
    gameweeks: list[tuple[int, str]],
    bank: float,
    free_transfers: int,
) -> None:
    if not 2 <= len(gameweeks) <= 6:
        raise ValueError("Planning horizon must contain two to six Gameweeks")
    if bank < 0:
        raise ValueError("Bank cannot be negative")
    if not 0 <= free_transfers <= MAX_FREE_TRANSFERS:
        raise ValueError("Free transfers must be between zero and five")
    if len({player.player_id for player in candidates}) != len(candidates):
        raise ValueError("Planning candidate IDs must be unique")
    current = [player for player in candidates if player.is_current]
    if len(current) != SQUAD_SIZE:
        raise ValueError("Current squad must contain exactly 15 planning candidates")
    if Counter(player.position for player in current) != Counter(POSITION_LIMITS):
        raise ValueError("Current squad has invalid positional quotas")
    if any(len(player.gameweek_xpts) != len(gameweeks) for player in candidates):
        raise ValueError("Every candidate requires one forecast per planned Gameweek")
    if any(player.buy_price <= 0 or player.selling_price <= 0 for player in candidates):
        raise ValueError("Planning prices must be positive")
