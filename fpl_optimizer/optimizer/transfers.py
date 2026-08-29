"""Exact constrained comparison of roll, one, and two transfers."""

from __future__ import annotations

from collections import Counter

from scipy.optimize import Bounds, LinearConstraint, milp  # type: ignore[import-untyped]

from fpl_optimizer.domain.transfers import (
    TransferCandidate,
    TransferEvaluation,
    TransferMove,
    TransferPlanResult,
)
from fpl_optimizer.optimizer.squad import MAX_PER_TEAM, POSITION_LIMITS, SQUAD_SIZE

TRANSFER_HIT = 4


def evaluate_transfers(
    candidates: list[TransferCandidate],
    *,
    bank: float,
    free_transfers: int,
    transfer_reluctance: int,
    horizon: int,
    max_transfers: int = 2,
    protected_player_ids: set[int] | None = None,
    must_sell_player_ids: set[int] | None = None,
    must_buy_player_ids: set[int] | None = None,
    excluded_player_ids: set[int] | None = None,
) -> TransferEvaluation:
    """Solve each exact transfer count and recommend action versus rolling."""

    protected = protected_player_ids or set()
    must_sell = must_sell_player_ids or set()
    must_buy = must_buy_player_ids or set()
    excluded = excluded_player_ids or set()
    current = _validate(
        candidates,
        bank=bank,
        free_transfers=free_transfers,
        transfer_reluctance=transfer_reluctance,
        horizon=horizon,
        max_transfers=max_transfers,
        protected_player_ids=protected,
        must_sell_player_ids=must_sell,
        must_buy_player_ids=must_buy,
        excluded_player_ids=excluded,
    )
    current_xpts = sum(player.horizon_xpts for player in current)
    roll = TransferPlanResult(
        transfers=0,
        moves=(),
        final_player_ids=tuple(sorted(player.player_id for player in current)),
        final_squad_xpts=current_xpts,
        gross_gain=0.0,
        hit_cost=0,
        net_gain=0.0,
        ending_bank=bank,
    )
    has_forced_move = bool(must_sell or must_buy)
    plans = [] if has_forced_move else [roll]
    for transfers in range(1, max_transfers + 1):
        plan = _solve_exact(
            candidates,
            transfers=transfers,
            bank=bank,
            free_transfers=free_transfers,
            current_xpts=current_xpts,
            protected_player_ids=protected,
            must_sell_player_ids=must_sell,
            must_buy_player_ids=must_buy,
            excluded_player_ids=excluded,
        )
        if plan is not None:
            plans.append(plan)

    roll_value = 0.5 + 0.025 * transfer_reluctance
    alternatives = [plan for plan in plans if plan.transfers > 0]
    if has_forced_move and not alternatives:
        raise ValueError("No legal transfer plan satisfies all scenario rules")
    best = max(alternatives, key=_plan_key) if alternatives else roll
    if has_forced_move and alternatives:
        recommendation = f"MAKE {best.transfers} TRANSFER" + ("S" if best.transfers != 1 else "")
        rationale = (
            f"The best legal plan satisfying the scenario rules changes {best.transfers} "
            f"player{'s' if best.transfers != 1 else ''} and adds {best.net_gain:.1f} net "
            f"projected points over {horizon} Gameweeks."
        )
        recommended_transfers = best.transfers
    elif best.net_gain > roll_value:
        recommendation = f"MAKE {best.transfers} TRANSFER" + ("S" if best.transfers != 1 else "")
        rationale = (
            f"The best {best.transfers}-transfer plan adds {best.gross_gain:.1f} projected "
            f"points over {horizon} Gameweeks, costs {best.hit_cost} points in hits, and clears "
            f"the {roll_value:.1f}-point flexibility threshold."
        )
        recommended_transfers = best.transfers
    else:
        recommendation = "ROLL TRANSFER"
        recommended_transfers = 0
        if alternatives:
            rationale = (
                f"The best available move adds {best.net_gain:.1f} net projected points over "
                f"{horizon} Gameweeks, below the {roll_value:.1f}-point value assigned to keeping "
                "transfer flexibility."
            )
        else:
            rationale = "No legal one- or two-transfer improvement is available, so rolling wins."
    return TransferEvaluation(
        recommendation=recommendation,
        recommended_transfers=recommended_transfers,
        rationale=rationale,
        horizon=horizon,
        free_transfers=free_transfers,
        starting_bank=bank,
        roll_flexibility_value=roll_value,
        current_squad_xpts=current_xpts,
        plans=tuple(plans),
    )


def _solve_exact(
    candidates: list[TransferCandidate],
    *,
    transfers: int,
    bank: float,
    free_transfers: int,
    current_xpts: float,
    protected_player_ids: set[int],
    must_sell_player_ids: set[int],
    must_buy_player_ids: set[int],
    excluded_player_ids: set[int],
) -> TransferPlanResult | None:
    count = len(candidates)
    current = [player for player in candidates if player.is_current]
    current_ids = {player.player_id for player in current}
    total_selling = sum(_selling_price(player) for player in current)
    objective = [
        -(player.horizon_xpts + 1e-7 * player.optimization_score + 1e-11 * (count - index))
        for index, player in enumerate(candidates)
    ]
    rows: list[list[float]] = []
    lower: list[float] = []
    upper: list[float] = []
    _add(rows, lower, upper, [1.0] * count, SQUAD_SIZE, SQUAD_SIZE)
    for position, required in POSITION_LIMITS.items():
        _add(
            rows,
            lower,
            upper,
            [1.0 if player.position == position else 0.0 for player in candidates],
            required,
            required,
        )
    for team in sorted({player.team for player in candidates}):
        _add(
            rows,
            lower,
            upper,
            [1.0 if player.team == team else 0.0 for player in candidates],
            0.0,
            MAX_PER_TEAM,
        )
    _add(
        rows,
        lower,
        upper,
        [1.0 if player.is_current else 0.0 for player in candidates],
        SQUAD_SIZE - transfers,
        SQUAD_SIZE - transfers,
    )
    budget_coefficients = [
        _selling_price(player) if player.is_current else player.buy_price
        for player in candidates
    ]
    _add(rows, lower, upper, budget_coefficients, 0.0, bank + total_selling)
    required_ids = protected_player_ids | must_buy_player_ids
    forbidden_ids = must_sell_player_ids | excluded_player_ids
    for index, player in enumerate(candidates):
        if player.player_id not in required_ids | forbidden_ids:
            continue
        coefficients = [0.0] * count
        coefficients[index] = 1.0
        target = 1.0 if player.player_id in required_ids else 0.0
        _add(rows, lower, upper, coefficients, target, target)
    solved = milp(
        c=objective,
        integrality=[1] * count,
        bounds=Bounds(0.0, 1.0),
        constraints=LinearConstraint(rows, lower, upper),
        options={"time_limit": 15.0, "mip_rel_gap": 0.0},
    )
    if not solved.success or solved.x is None:
        return None
    final = [
        player
        for player, selected in zip(candidates, solved.x, strict=True)
        if selected > 0.5
    ]
    final_ids = {player.player_id for player in final}
    outgoing = [player for player in current if player.player_id not in final_ids]
    incoming = [player for player in final if player.player_id not in current_ids]
    if len(outgoing) != transfers or len(incoming) != transfers:
        raise RuntimeError("Solver returned an invalid transfer count")
    moves = _pair_moves(outgoing, incoming)
    gross_gain = sum(player.horizon_xpts for player in final) - current_xpts
    hit_cost = max(0, transfers - free_transfers) * TRANSFER_HIT
    ending_bank = bank + sum(_selling_price(player) for player in outgoing) - sum(
        player.buy_price for player in incoming
    )
    return TransferPlanResult(
        transfers=transfers,
        moves=moves,
        final_player_ids=tuple(sorted(final_ids)),
        final_squad_xpts=sum(player.horizon_xpts for player in final),
        gross_gain=gross_gain,
        hit_cost=hit_cost,
        net_gain=gross_gain - hit_cost,
        ending_bank=ending_bank,
    )


def _pair_moves(
    outgoing: list[TransferCandidate], incoming: list[TransferCandidate]
) -> tuple[TransferMove, ...]:
    moves: list[TransferMove] = []
    for position in POSITION_LIMITS:
        outs = sorted(
            (player for player in outgoing if player.position == position),
            key=lambda player: player.player_id,
        )
        ins = sorted(
            (player for player in incoming if player.position == position),
            key=lambda player: (-player.horizon_xpts, player.player_id),
        )
        if len(outs) != len(ins):
            raise RuntimeError("Transfers could not be paired by position")
        for sold, bought in zip(outs, ins, strict=True):
            selling_price = _selling_price(sold)
            moves.append(
                TransferMove(
                    out_player_id=sold.player_id,
                    out_player=sold.player,
                    out_team=sold.team,
                    selling_price=selling_price,
                    in_player_id=bought.player_id,
                    in_player=bought.player,
                    in_team=bought.team,
                    buy_price=bought.buy_price,
                    position=position,
                    budget_change=selling_price - bought.buy_price,
                    horizon_xpts_gain=bought.horizon_xpts - sold.horizon_xpts,
                )
            )
    return tuple(moves)


def _validate(
    candidates: list[TransferCandidate],
    *,
    bank: float,
    free_transfers: int,
    transfer_reluctance: int,
    horizon: int,
    max_transfers: int,
    protected_player_ids: set[int],
    must_sell_player_ids: set[int],
    must_buy_player_ids: set[int],
    excluded_player_ids: set[int],
) -> list[TransferCandidate]:
    if bank < 0:
        raise ValueError("Bank cannot be negative")
    if not 0 <= free_transfers <= 5:
        raise ValueError("Free transfers must be between zero and five")
    if not 0 <= transfer_reluctance <= 100:
        raise ValueError("Transfer reluctance must be between zero and 100")
    if not 1 <= horizon <= 6:
        raise ValueError("Planning horizon must be between one and six Gameweeks")
    if not 0 <= max_transfers <= 2:
        raise ValueError("Transfer comparison supports at most two transfers")
    ids = [player.player_id for player in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("Transfer candidate IDs must be unique")
    current = [player for player in candidates if player.is_current]
    if len(current) != SQUAD_SIZE:
        raise ValueError("Current squad must contain exactly 15 transfer candidates")
    positions = Counter(player.position for player in current)
    if positions != Counter(POSITION_LIMITS):
        raise ValueError("Current squad has invalid positional quotas")
    teams = Counter(player.team for player in current)
    if any(count > MAX_PER_TEAM for count in teams.values()):
        raise ValueError("Current squad exceeds the three-player club limit")
    if any(player.selling_price is None or player.selling_price <= 0 for player in current):
        raise ValueError("Every current player requires a positive selling price")
    all_ids = set(ids)
    current_ids = {player.player_id for player in current}
    constrained = (
        protected_player_ids
        | must_sell_player_ids
        | must_buy_player_ids
        | excluded_player_ids
    )
    if constrained - all_ids:
        raise ValueError("Scenario transfer rules contain unknown players")
    if protected_player_ids - current_ids or must_sell_player_ids - current_ids:
        raise ValueError("Protected and must-sell players must belong to the current squad")
    if must_buy_player_ids & current_ids:
        raise ValueError("Must-buy players must be outside the current squad")
    if protected_player_ids & must_sell_player_ids:
        raise ValueError("A player cannot be both protected and marked must sell")
    if must_buy_player_ids & excluded_player_ids:
        raise ValueError("A player cannot be both must buy and excluded")
    if len(must_buy_player_ids) > max_transfers or len(must_sell_player_ids) > max_transfers:
        raise ValueError("Scenario rules require more transfers than the selected maximum")
    return current


def _selling_price(player: TransferCandidate) -> float:
    if player.selling_price is None:
        raise ValueError(f"Missing selling price for {player.player}")
    return player.selling_price


def _plan_key(plan: TransferPlanResult) -> tuple[float, float, int]:
    return plan.net_gain, plan.gross_gain, -plan.transfers


def _add(
    rows: list[list[float]],
    lower: list[float],
    upper: list[float],
    coefficients: list[float],
    minimum: float,
    maximum: float,
) -> None:
    rows.append(coefficients)
    lower.append(minimum)
    upper.append(maximum)
