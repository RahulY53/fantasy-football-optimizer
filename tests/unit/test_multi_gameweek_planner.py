"""Tests for joint transfer, lineup, captain, and free-transfer planning."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

import pytest

from fpl_optimizer.domain.planner import PlanningCandidate
from fpl_optimizer.optimizer.planner import optimize_multi_gameweek
from fpl_optimizer.optimizer.squad import POSITION_LIMITS


def planning_pool() -> list[PlanningCandidate]:
    """Return a legal squad plus one future-focused midfield upgrade."""

    positions = ["GK"] * 2 + ["DEF"] * 5 + ["MID"] * 5 + ["FWD"] * 3
    candidates = [
        PlanningCandidate(
            player_id=index + 1,
            player=f"Current {position} {index}",
            position=position,
            team=f"T{index % 5}",
            buy_price=5.0,
            selling_price=5.0,
            optimization_score=50.0,
            is_current=True,
            gameweek_xpts=(5.0, 5.0, 5.0),
        )
        for index, position in enumerate(positions)
    ]
    candidates.append(
        PlanningCandidate(
            player_id=100,
            player="Future Midfielder",
            position="MID",
            team="UPG",
            buy_price=5.0,
            selling_price=5.0,
            optimization_score=80.0,
            is_current=False,
            gameweek_xpts=(0.0, 20.0, 20.0),
        )
    )
    return candidates


def test_joint_planner_delays_move_and_carries_free_transfers() -> None:
    plan = optimize_multi_gameweek(
        planning_pool(),
        gameweeks=[(1, "GW1"), (2, "GW2"), (3, "GW3")],
        bank=0.0,
        free_transfers=1,
    )

    assert [len(week.transfers) for week in plan.weeks] == [0, 1, 0]
    assert plan.weeks[0].free_transfers_after == 2
    assert plan.weeks[1].free_transfers_before == 2
    assert plan.weeks[1].transfers[0].in_player == "Future Midfielder"
    assert plan.total_hits == 0
    assert plan.net_projected_points == pytest.approx(plan.gross_projected_points)
    for week in plan.weeks:
        squad = [p for p in planning_pool() if p.player_id in week.squad_ids]
        assert len(squad) == 15
        assert Counter(player.position for player in squad) == Counter(POSITION_LIMITS)
        assert len(week.starter_ids) == 11
        assert week.captain_id in week.starter_ids


def test_joint_planner_caps_rolled_free_transfers_at_five() -> None:
    current_only = planning_pool()[:-1]
    plan = optimize_multi_gameweek(
        current_only,
        gameweeks=[(1, "GW1"), (2, "GW2"), (3, "GW3")],
        bank=0.0,
        free_transfers=5,
    )

    assert plan.total_transfers == 0
    assert [week.free_transfers_after for week in plan.weeks] == [5, 5, 5]


def test_joint_planner_validates_horizon_and_forecast_alignment() -> None:
    with pytest.raises(ValueError, match="two to six"):
        optimize_multi_gameweek(
            planning_pool(), gameweeks=[(1, "GW1")], bank=0, free_transfers=1
        )
    malformed = planning_pool()
    malformed[0] = replace(malformed[0], gameweek_xpts=(1.0, 2.0))
    with pytest.raises(ValueError, match="one forecast"):
        optimize_multi_gameweek(
            malformed,
            gameweeks=[(1, "GW1"), (2, "GW2"), (3, "GW3")],
            bank=0,
            free_transfers=1,
        )
