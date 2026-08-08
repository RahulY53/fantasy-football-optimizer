"""Tests for legal formation, captaincy, and bench optimization."""

from __future__ import annotations

from collections import Counter

import pytest

from fpl_optimizer.domain.team import LineupCandidate
from fpl_optimizer.optimizer.lineup import optimize_lineup, validate_lineup


def candidate(
    player_id: int,
    position: str,
    index: int,
    xpts: float,
    *,
    minutes: float = 90.0,
    risk: float = 20.0,
) -> LineupCandidate:
    """Create one synthetic current-squad forecast."""

    return LineupCandidate(
        player_id=player_id,
        player=f"{position} {index}",
        position=position,
        team=f"T{player_id % 8}",
        opponent="OPP (H)",
        current_price=6.0,
        selling_price=6.0,
        expected_minutes=minutes,
        next_gw_xpts=xpts,
        next_3_xpts=xpts * 3,
        next_5_xpts=xpts * 5,
        attacking_xpts=xpts / 2,
        ownership=float(index * 5),
        risk=risk,
    )


def legal_squad() -> list[LineupCandidate]:
    """Build a squad whose optimal formation is 3-5-2."""

    values = {
        "GK": [5, 4],
        "DEF": [6, 5, 4, 0.8, 0.7],
        "MID": [10, 9, 8, 7, 1],
        "FWD": [12, 11, 0.5],
    }
    players: list[LineupCandidate] = []
    player_id = 1
    for position, projections in values.items():
        for index, xpts in enumerate(projections):
            players.append(candidate(player_id, position, index, xpts))
            player_id += 1
    return players


def test_lineup_selects_best_legal_formation_and_roles() -> None:
    result = optimize_lineup(legal_squad())

    validate_lineup(result)
    assert result.formation == "3-5-2"
    assert len(result.starters) == 11
    assert len(result.bench) == 4
    assert Counter(player.position for player in result.starters) == {
        "GK": 1,
        "DEF": 3,
        "MID": 5,
        "FWD": 2,
    }
    captain = next(player for player in result.starters if player.player_id == result.captain_id)
    vice = next(player for player in result.starters if player.player_id == result.vice_captain_id)
    assert captain.next_gw_xpts == 12
    assert vice.player_id != captain.player_id
    assert result.projected_points == pytest.approx(result.base_xpts + captain.next_gw_xpts)
    assert [player.position for player in result.bench][-1] == "GK"
    assert [player.next_gw_xpts for player in result.bench[:3]] == [0.8, 0.7, 0.5]
    assert {option.kind for option in result.captain_options} == {
        "Best expected",
        "Safest",
        "Highest ceiling",
        "Best differential",
    }


def test_safest_captain_can_differ_from_best_expected() -> None:
    squad = legal_squad()
    highest = max(squad, key=lambda player: player.next_gw_xpts)
    squad = [
        candidate(
            player.player_id,
            player.position,
            player.player_id,
            player.next_gw_xpts,
            minutes=55 if player.player_id == highest.player_id else 90,
            risk=70 if player.player_id == highest.player_id else 10,
        )
        for player in squad
    ]
    result = optimize_lineup(squad)
    views = {option.kind: option.player_id for option in result.captain_options}

    assert views["Best expected"] == highest.player_id
    assert views["Safest"] != highest.player_id


def test_lineup_rejects_incomplete_squad() -> None:
    with pytest.raises(ValueError, match="exactly 15"):
        optimize_lineup(legal_squad()[:-1])
