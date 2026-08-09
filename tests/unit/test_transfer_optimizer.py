"""Tests for roll, one-transfer, two-transfer, and hit evaluation."""

from __future__ import annotations

import pytest

from fpl_optimizer.domain.transfers import TransferCandidate
from fpl_optimizer.optimizer.transfers import evaluate_transfers


def transfer_pool(upgrade: float = 8.0) -> list[TransferCandidate]:
    """Build a legal current squad plus affordable alternatives."""

    positions = ["GK"] * 2 + ["DEF"] * 5 + ["MID"] * 5 + ["FWD"] * 3
    players: list[TransferCandidate] = []
    for index, position in enumerate(positions):
        players.append(
            TransferCandidate(
                player_id=index + 1,
                player=f"Current {position} {index}",
                position=position,
                team=f"T{index % 5}",
                buy_price=5.0,
                selling_price=5.0,
                horizon_xpts=10.0 + index / 100,
                optimization_score=50.0,
                is_current=True,
            )
        )
    player_id = 100
    for position in ("GK", "DEF", "MID", "FWD"):
        for index in range(3):
            players.append(
                TransferCandidate(
                    player_id=player_id,
                    player=f"Upgrade {position} {index}",
                    position=position,
                    team=f"U{index}",
                    buy_price=5.0,
                    selling_price=None,
                    horizon_xpts=18.0 + upgrade + index / 10,
                    optimization_score=80.0,
                    is_current=False,
                )
            )
            player_id += 1
    return players


def test_transfer_evaluation_compares_roll_one_two_and_hits() -> None:
    result = evaluate_transfers(
        transfer_pool(),
        bank=0.0,
        free_transfers=1,
        transfer_reluctance=50,
        horizon=3,
    )

    assert [plan.transfers for plan in result.plans] == [0, 1, 2]
    one = result.plans[1]
    two = result.plans[2]
    assert one.hit_cost == 0
    assert two.hit_cost == 4
    assert len(one.moves) == 1
    assert len(two.moves) == 2
    assert one.ending_bank == pytest.approx(0.0)
    assert two.net_gain == pytest.approx(two.gross_gain - 4)
    assert result.recommended_transfers == 2
    assert result.recommendation == "MAKE 2 TRANSFERS"


def test_transfer_reluctance_can_make_roll_the_best_decision() -> None:
    candidates = transfer_pool(upgrade=-7.9)
    result = evaluate_transfers(
        candidates,
        bank=0.0,
        free_transfers=2,
        transfer_reluctance=100,
        horizon=3,
    )

    assert result.roll_flexibility_value == 3.0
    assert result.recommendation == "ROLL TRANSFER"
    assert result.recommended_transfers == 0
    assert "flexibility" in result.rationale


def test_transfer_optimizer_validates_current_squad_and_transfer_limit() -> None:
    with pytest.raises(ValueError, match="exactly 15"):
        evaluate_transfers(
            transfer_pool()[1:],
            bank=0,
            free_transfers=1,
            transfer_reluctance=50,
            horizon=3,
        )
    with pytest.raises(ValueError, match="at most two"):
        evaluate_transfers(
            transfer_pool(),
            bank=0,
            free_transfers=1,
            transfer_reluctance=50,
            horizon=3,
            max_transfers=3,
        )


def test_transfer_scenario_enforces_protect_sell_buy_and_exclude_rules() -> None:
    result = evaluate_transfers(
        transfer_pool(),
        bank=0,
        free_transfers=2,
        transfer_reluctance=50,
        horizon=3,
        protected_player_ids={1},
        must_sell_player_ids={3},
        must_buy_player_ids={102},
        excluded_player_ids={101},
    )

    assert result.plans
    assert all(1 in plan.final_player_ids for plan in result.plans)
    assert all(3 not in plan.final_player_ids for plan in result.plans)
    assert all(102 in plan.final_player_ids for plan in result.plans)
    assert all(101 not in plan.final_player_ids for plan in result.plans)
    assert result.recommended_transfers > 0


def test_transfer_scenario_rejects_contradictory_rules() -> None:
    with pytest.raises(ValueError, match="both protected and marked must sell"):
        evaluate_transfers(
            transfer_pool(),
            bank=0,
            free_transfers=1,
            transfer_reluctance=50,
            horizon=3,
            protected_player_ids={1},
            must_sell_player_ids={1},
        )
