"""Tests for independent Wildcard, Free Hit, Bench Boost, and Triple Captain evaluation."""

from __future__ import annotations

from fpl_optimizer.domain.chips import ChipCandidate
from fpl_optimizer.optimizer.chips import evaluate_chips


def chip_pool() -> tuple[list[ChipCandidate], set[int]]:
    """Build a legal current squad and position-matched chip upgrades."""

    positions = ["GK"] * 2 + ["DEF"] * 5 + ["MID"] * 5 + ["FWD"] * 3
    candidates = [
        ChipCandidate(
            player_id=index + 1,
            player=f"Current {position} {index}",
            position=position,
            team=f"T{index % 5}",
            price=5.0,
            optimization_score=50.0,
            gameweek_xpts=(3.0 + index / 20, 3.0 + index / 20, 3.0 + index / 20),
        )
        for index, position in enumerate(positions)
    ]
    for index, position in enumerate(("GK", "DEF", "MID", "FWD")):
        candidates.append(
            ChipCandidate(
                player_id=100 + index,
                player=f"Upgrade {position}",
                position=position,
                team=f"U{index}",
                price=5.0,
                optimization_score=80.0,
                gameweek_xpts=(4.0, 12.0 + index, 5.0),
            )
        )
    return candidates, set(range(1, 16))


def test_chip_evaluation_returns_all_opportunities_and_best_timing() -> None:
    candidates, current_ids = chip_pool()
    result = evaluate_chips(
        candidates,
        current_ids=current_ids,
        budget=75.0,
        gameweeks=[(1, "GW1"), (2, "GW2"), (3, "GW3")],
        availability={
            "Wildcard": True,
            "Free Hit": True,
            "Bench Boost": True,
            "Triple Captain": True,
        },
    )

    assert {opportunity.chip for opportunity in result.opportunities} == {
        "Wildcard",
        "Free Hit",
        "Bench Boost",
        "Triple Captain",
    }
    free_hit = next(item for item in result.opportunities if item.chip == "Free Hit")
    wildcard = next(item for item in result.opportunities if item.chip == "Wildcard")
    assert free_hit.recommended_gameweek == "GW2"
    assert free_hit.projected_gain > 0
    assert len(free_hit.weeks[0].squad_ids) == 15
    assert len(free_hit.weeks[0].starter_ids) == 11
    assert free_hit.weeks[0].captain_id in free_hit.weeks[0].starter_ids
    assert wildcard.players_in
    assert wildcard.projected_gain > 0
    assert result.best_chip is not None


def test_unavailable_chip_is_not_selected_as_best() -> None:
    candidates, current_ids = chip_pool()
    result = evaluate_chips(
        candidates,
        current_ids=current_ids,
        budget=75.0,
        gameweeks=[(1, "GW1"), (2, "GW2"), (3, "GW3")],
        availability={
            "Wildcard": False,
            "Free Hit": False,
            "Bench Boost": True,
            "Triple Captain": False,
        },
    )

    assert result.best_chip == "Bench Boost"
    assert next(item for item in result.opportunities if item.chip == "Free Hit").available is False
