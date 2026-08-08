"""Tests for the Phase 5 initial-squad integer program."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

import pytest

from fpl_optimizer.domain.optimizer import SquadCandidate, SquadOptimizationRequest
from fpl_optimizer.optimizer.squad import POSITION_LIMITS, optimize_squad, validate_result


def candidate_pool() -> list[SquadCandidate]:
    """Build a legal synthetic market with alternatives at every position."""

    players: list[SquadCandidate] = []
    player_id = 1
    for position, count, base_price in (
        ("GK", 4, 4.0),
        ("DEF", 10, 4.0),
        ("MID", 10, 5.0),
        ("FWD", 6, 5.5),
    ):
        for index in range(count):
            players.append(
                SquadCandidate(
                    player_id=player_id,
                    player=f"{position} {index}",
                    position=position,
                    team=f"T{index % 10}",
                    price=base_price + 0.1 * index,
                    ownership=2.0 * index,
                    horizon_xpts=5.0 + index,
                    risk=20.0,
                    optimization_score=40.0 + 2.0 * index,
                )
            )
            player_id += 1
    return players


def test_optimizer_builds_legal_squad_with_lock_and_exclusion() -> None:
    candidates = candidate_pool()
    locked = candidates[0]
    excluded = max(
        (player for player in candidates if player.position == "MID"),
        key=lambda player: player.optimization_score,
    )
    result = optimize_squad(
        candidates,
        SquadOptimizationRequest(
            budget=100.0,
            locked_player_ids=(locked.player_id,),
            excluded_player_ids=(excluded.player_id,),
        ),
    )

    validate_result(result)
    assert len(result.players) == 15
    assert Counter(player.position for player in result.players) == Counter(POSITION_LIMITS)
    assert max(Counter(player.team for player in result.players).values()) <= 3
    assert result.total_cost <= 100.0
    assert locked.player_id in {player.player_id for player in result.players}
    assert excluded.player_id not in {player.player_id for player in result.players}
    assert next(player for player in result.players if player.player_id == locked.player_id).locked


def test_optimizer_rejects_conflicting_or_impossible_constraints() -> None:
    candidates = candidate_pool()
    player_id = candidates[0].player_id
    with pytest.raises(ValueError, match="both locked and excluded"):
        optimize_squad(
            candidates,
            SquadOptimizationRequest(
                locked_player_ids=(player_id,), excluded_player_ids=(player_id,)
            ),
        )
    with pytest.raises(ValueError, match="infeasible"):
        optimize_squad(candidates, SquadOptimizationRequest(budget=10.0))


def test_optimizer_rejects_four_locked_players_from_one_club() -> None:
    candidates = candidate_pool()
    locked_ids = {1, 5, 15, 25}
    adjusted = [
        replace(player, team="SAME") if player.player_id in locked_ids else player
        for player in candidates
    ]
    with pytest.raises(ValueError, match="three-player club limit"):
        optimize_squad(
            adjusted,
            SquadOptimizationRequest(locked_player_ids=tuple(sorted(locked_ids))),
        )
