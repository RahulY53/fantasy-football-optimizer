"""Tests for session-only forecast assumptions."""

import pytest

from fpl_optimizer.domain.scenarios import ScenarioAssumptions
from fpl_optimizer.domain.strategy import PlayerStrategyInput
from fpl_optimizer.domain.transfers import TransferCandidate
from fpl_optimizer.services.scenarios import (
    apply_assumptions,
    prune_dominated_transfer_candidates,
)


def player_input(player_id: int = 1, team: str = "ARS") -> PlayerStrategyInput:
    return PlayerStrategyInput(
        player_id=player_id,
        player=f"Player {player_id}",
        position="MID",
        team=team,
        price=8.0,
        ownership=20.0,
        form=5.0,
        status="a",
        chance_next_round=100,
        horizon_xpts=30.0,
        week_xpts=(10.0, 10.0, 10.0),
        expected_minutes=90.0,
        fixture_quality=3.0,
        attacking_xpts=18.0,
        clean_sheet_xpts=3.0,
        bonus_xpts=3.0,
        confidence=1.0,
        defensive_contribution_xpts=1.0,
    )


def test_start_and_team_attack_assumptions_adjust_copies_only() -> None:
    baseline = player_input()
    scenario = apply_assumptions(
        [baseline],
        ScenarioAssumptions(
            start_player_id=1,
            start_probability=60,
            attack_team="ARS",
            attack_change=-10,
        ),
    )[0]

    assert baseline.horizon_xpts == 30.0
    assert scenario.expected_minutes == pytest.approx(62.0)
    assert scenario.attacking_xpts < baseline.attacking_xpts
    assert scenario.horizon_xpts < baseline.horizon_xpts
    assert sum(scenario.week_xpts) == pytest.approx(scenario.horizon_xpts)


def test_unavailable_assumption_zeroes_forecast_components() -> None:
    scenario = apply_assumptions(
        [player_input()], ScenarioAssumptions(unavailable_player_ids=(1,))
    )[0]

    assert scenario.horizon_xpts == 0
    assert scenario.week_xpts == (0.0, 0.0, 0.0)
    assert scenario.expected_minutes == 0
    assert scenario.status == "u"


def test_transfer_screen_removes_only_unconstrained_same_club_dominance() -> None:
    def candidate(
        player_id: int, team: str, price: float, xpts: float, score: float
    ) -> TransferCandidate:
        return TransferCandidate(
            player_id=player_id,
            player=f"Player {player_id}",
            position="MID",
            team=team,
            buy_price=price,
            selling_price=None,
            horizon_xpts=xpts,
            optimization_score=score,
            is_current=False,
        )

    pool = [
        candidate(1, "ARS", 7.0, 20.0, 60.0),
        candidate(2, "ARS", 8.0, 19.0, 55.0),
        candidate(3, "CHE", 8.0, 19.0, 55.0),
    ]

    result = prune_dominated_transfer_candidates(pool, {2})

    assert {item.player_id for item in result} == {1, 2, 3}
    assert {item.player_id for item in prune_dominated_transfer_candidates(pool, set())} == {
        1,
        3,
    }
