"""Tests for the weekly decision-card composition layer."""

from __future__ import annotations

from dataclasses import replace

from fpl_optimizer.domain.chips import ChipEvaluation, ChipOpportunity
from fpl_optimizer.domain.planner import MultiGameweekPlan, PlannedGameweek
from fpl_optimizer.domain.simulation import SimulationResult
from fpl_optimizer.domain.team import LineupPlayer, LineupResult
from fpl_optimizer.domain.transfers import (
    TransferEvaluation,
    TransferMove,
    TransferPlanResult,
)
from fpl_optimizer.services.weekly import build_weekly_summary


def test_weekly_summary_explains_transfer_confidence_and_risk() -> None:
    lineup = _lineup()
    transfers = _transfers()
    summary = build_weekly_summary(
        lineup,
        transfers,
        _planner(),
        _simulation(),
        _chips(),
    )

    assert summary.action == "MAKE 1 TRANSFER"
    assert summary.action_kind == "Transfer"
    assert summary.alternative == "Roll transfer"
    assert summary.alternative_gain == 0.0
    assert summary.captain == "Player 1"
    assert summary.vice_captain == "Player 2"
    assert summary.projected_score == 60.0
    assert 0.0 <= summary.confidence_score <= 100.0
    assert summary.confidence_label in {"Low", "Medium", "High"}
    assert summary.risk_label in {"Low", "Medium", "High"}
    assert [factor.label for factor in summary.confidence_factors] == [
        "Decision clarity",
        "Lineup reliability",
        "Simulation certainty",
    ]


def test_current_gameweek_chip_can_override_transfer_action() -> None:
    opportunity = ChipOpportunity(
        chip="Bench Boost",
        available=True,
        recommended_gameweek="GW1",
        projected_gain=6.0,
        rationale="The current bench has an unusually strong fixture set.",
        players_in=(),
        players_out=(),
        weeks=(),
    )
    chips = ChipEvaluation(
        horizon=3,
        budget=100.0,
        current_projected_points=150.0,
        best_chip="Bench Boost",
        best_gain=6.0,
        opportunities=(opportunity,),
    )

    summary = build_weekly_summary(
        _lineup(),
        _transfers(),
        _planner(),
        _simulation(),
        chips,
    )

    assert summary.action == "PLAY BENCH BOOST"
    assert summary.action_kind == "Chip"
    assert summary.rationale == opportunity.rationale


def _lineup() -> LineupResult:
    players = tuple(
        LineupPlayer(
            player_id=index,
            player=f"Player {index}",
            position=("GK" if index == 1 else "DEF" if index <= 4 else "MID"),
            team=f"T{index}",
            opponent="OPP (H)",
            current_price=5.0,
            expected_minutes=80.0,
            next_gw_xpts=5.0,
            ownership=10.0,
            risk=20.0,
            role="Captain" if index == 1 else "Vice captain" if index == 2 else "Starter",
            bench_order=None,
        )
        for index in range(1, 12)
    )
    bench = tuple(
        replace(player, player_id=player.player_id + 11, role="Bench", bench_order=index)
        for index, player in enumerate(players[:4], start=1)
    )
    return LineupResult(
        formation="3-5-2",
        starters=players,
        bench=bench,
        captain_id=1,
        vice_captain_id=2,
        base_xpts=55.0,
        projected_points=60.0,
        next_3_squad_xpts=180.0,
        next_5_squad_xpts=290.0,
        captain_options=(),
    )


def _transfers() -> TransferEvaluation:
    move = TransferMove(
        out_player_id=12,
        out_player="Player 12",
        out_team="T12",
        selling_price=5.0,
        in_player_id=20,
        in_player="Upgrade",
        in_team="NEW",
        buy_price=5.5,
        position="MID",
        budget_change=0.5,
        horizon_xpts_gain=5.0,
    )
    roll = TransferPlanResult(0, (), tuple(range(1, 16)), 150.0, 0.0, 0, 0.0, 1.0)
    transfer = TransferPlanResult(
        1,
        (move,),
        tuple(range(1, 15)) + (20,),
        155.0,
        5.0,
        0,
        5.0,
        0.5,
    )
    return TransferEvaluation(
        recommendation="MAKE 1 TRANSFER",
        recommended_transfers=1,
        rationale="The upgrade clears the transfer-flexibility threshold.",
        horizon=3,
        free_transfers=1,
        starting_bank=1.0,
        roll_flexibility_value=1.5,
        current_squad_xpts=150.0,
        plans=(roll, transfer),
    )


def _planner() -> MultiGameweekPlan:
    week = PlannedGameweek(
        gameweek_id=1,
        gameweek="GW1",
        transfers=(),
        free_transfers_before=1,
        free_transfers_after=2,
        hit_cost=0,
        bank_after=1.0,
        formation="3-5-2",
        captain_id=1,
        captain="Player 1",
        starter_ids=tuple(range(1, 12)),
        squad_ids=tuple(range(1, 16)),
        lineup_xpts=55.0,
        captain_xpts=5.0,
        projected_points=60.0,
        net_projected_points=60.0,
    )
    return MultiGameweekPlan(
        status="Optimal",
        solver="Test",
        horizon=3,
        starting_bank=1.0,
        starting_free_transfers=1,
        total_transfers=0,
        total_hits=0,
        gross_projected_points=180.0,
        net_projected_points=180.0,
        weeks=(week,),
    )


def _simulation() -> SimulationResult:
    return SimulationResult(
        iterations=2_500,
        seed=42,
        horizon=3,
        mean=180.0,
        median=178.0,
        standard_deviation=24.0,
        p10=150.0,
        p25=165.0,
        p75=195.0,
        p90=212.0,
        probability_below_40_per_gw=0.1,
        probability_50_per_gw_plus=0.7,
        probability_60_per_gw_plus=0.4,
        weeks=(),
        players=(),
        histogram=(),
    )


def _chips() -> ChipEvaluation:
    return ChipEvaluation(
        horizon=3,
        budget=100.0,
        current_projected_points=150.0,
        best_chip=None,
        best_gain=0.0,
        opportunities=(),
    )
