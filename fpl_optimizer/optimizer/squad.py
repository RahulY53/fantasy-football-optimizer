"""Binary integer program for an initial legal FPL squad."""

from __future__ import annotations

from collections import Counter

from scipy.optimize import Bounds, LinearConstraint, milp  # type: ignore[import-untyped]

from fpl_optimizer.domain.optimizer import (
    SquadCandidate,
    SquadOptimizationRequest,
    SquadOptimizationResult,
    SquadPlayer,
)

POSITION_LIMITS = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}
SQUAD_SIZE = 15
MAX_PER_TEAM = 3
SOLVER_NAME = "scipy-highs-milp"


def optimize_squad(
    candidates: list[SquadCandidate], request: SquadOptimizationRequest
) -> SquadOptimizationResult:
    """Maximize strategy utility subject to official initial-squad constraints."""

    _validate(candidates, request)
    count = len(candidates)
    objective = [
        -(candidate.optimization_score + 1e-6 * candidate.horizon_xpts + 1e-10 * (count - i))
        for i, candidate in enumerate(candidates)
    ]
    rows: list[list[float]] = []
    lower: list[float] = []
    upper: list[float] = []

    _add_constraint(rows, lower, upper, [1.0] * count, SQUAD_SIZE, SQUAD_SIZE)
    for position, required in POSITION_LIMITS.items():
        coefficients = [1.0 if item.position == position else 0.0 for item in candidates]
        _add_constraint(rows, lower, upper, coefficients, required, required)
    for team in sorted({item.team for item in candidates}):
        coefficients = [1.0 if item.team == team else 0.0 for item in candidates]
        _add_constraint(rows, lower, upper, coefficients, 0.0, MAX_PER_TEAM)
    _add_constraint(
        rows,
        lower,
        upper,
        [item.price for item in candidates],
        0.0,
        request.budget,
    )
    locked = set(request.locked_player_ids)
    excluded = set(request.excluded_player_ids)
    for index, candidate in enumerate(candidates):
        if candidate.player_id not in locked | excluded:
            continue
        coefficients = [0.0] * count
        coefficients[index] = 1.0
        target = 1.0 if candidate.player_id in locked else 0.0
        _add_constraint(rows, lower, upper, coefficients, target, target)

    solved = milp(
        c=objective,
        integrality=[1] * count,
        bounds=Bounds(0.0, 1.0),
        constraints=LinearConstraint(rows, lower, upper),
        options={"time_limit": 15.0, "mip_rel_gap": 0.0},
    )
    if not solved.success or solved.x is None:
        reason = solved.message or "No legal squad satisfies these constraints"
        raise ValueError(f"Squad optimization is infeasible: {reason}")
    selected_candidates = [
        candidate
        for candidate, selected in zip(candidates, solved.x, strict=True)
        if selected > 0.5
    ]
    if len(selected_candidates) != SQUAD_SIZE:
        raise RuntimeError("Solver returned an invalid squad size")
    selected = tuple(
        SquadPlayer(
            player_id=item.player_id,
            player=item.player,
            position=item.position,
            team=item.team,
            price=item.price,
            ownership=item.ownership,
            horizon_xpts=item.horizon_xpts,
            risk=item.risk,
            optimization_score=item.optimization_score,
            locked=item.player_id in locked,
        )
        for item in sorted(
            selected_candidates,
            key=lambda player: (
                list(POSITION_LIMITS).index(player.position),
                -player.optimization_score,
                player.player,
            ),
        )
    )
    total_cost = sum(item.price for item in selected)
    return SquadOptimizationResult(
        status="Optimal",
        solver=SOLVER_NAME,
        players=selected,
        budget=request.budget,
        total_cost=total_cost,
        budget_remaining=request.budget - total_cost,
        objective_score=sum(item.optimization_score for item in selected),
        total_xpts=sum(item.horizon_xpts for item in selected),
        average_ownership=sum(item.ownership for item in selected) / SQUAD_SIZE,
        average_risk=sum(item.risk for item in selected) / SQUAD_SIZE,
    )


def validate_result(result: SquadOptimizationResult) -> None:
    """Raise if a returned result violates an official squad constraint."""

    if len(result.players) != SQUAD_SIZE:
        raise ValueError("Squad must contain exactly 15 players")
    positions = Counter(player.position for player in result.players)
    if positions != Counter(POSITION_LIMITS):
        raise ValueError("Squad has invalid positional quotas")
    teams = Counter(player.team for player in result.players)
    if any(count > MAX_PER_TEAM for count in teams.values()):
        raise ValueError("Squad exceeds the three-player club limit")
    if result.total_cost > result.budget + 1e-7:
        raise ValueError("Squad exceeds the available budget")


def _validate(candidates: list[SquadCandidate], request: SquadOptimizationRequest) -> None:
    if request.budget <= 0:
        raise ValueError("Budget must be greater than zero")
    ids = [candidate.player_id for candidate in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("Candidate player IDs must be unique")
    invalid_positions = sorted({item.position for item in candidates} - set(POSITION_LIMITS))
    if invalid_positions:
        raise ValueError(f"Unknown positions: {', '.join(invalid_positions)}")
    available_positions = Counter(item.position for item in candidates)
    for position, required in POSITION_LIMITS.items():
        if available_positions[position] < required:
            raise ValueError(f"Not enough {position} candidates to build a legal squad")
    locked = set(request.locked_player_ids)
    excluded = set(request.excluded_player_ids)
    overlap = locked & excluded
    if overlap:
        raise ValueError("A player cannot be both locked and excluded")
    unknown = (locked | excluded) - set(ids)
    if unknown:
        raise ValueError(f"Unknown constrained player IDs: {', '.join(map(str, sorted(unknown)))}")
    if len(locked) > SQUAD_SIZE:
        raise ValueError("Cannot lock more than 15 players")
    locked_players = [item for item in candidates if item.player_id in locked]
    locked_positions = Counter(item.position for item in locked_players)
    for position, count in locked_positions.items():
        if count > POSITION_LIMITS[position]:
            raise ValueError(f"Too many locked {position} players")
    locked_teams = Counter(item.team for item in locked_players)
    if any(count > MAX_PER_TEAM for count in locked_teams.values()):
        raise ValueError("Locked players exceed the three-player club limit")
    if sum(item.price for item in locked_players) > request.budget:
        raise ValueError("Locked players alone exceed the available budget")


def _add_constraint(
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
