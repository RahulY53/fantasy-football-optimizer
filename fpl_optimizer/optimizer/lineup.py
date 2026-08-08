"""Exact legal-formation search and transparent captaincy selection."""

from __future__ import annotations

from collections import Counter

from fpl_optimizer.domain.team import (
    CaptainOption,
    LineupCandidate,
    LineupPlayer,
    LineupResult,
)
from fpl_optimizer.optimizer.squad import POSITION_LIMITS

LEGAL_FORMATIONS = (
    (3, 4, 3),
    (3, 5, 2),
    (4, 3, 3),
    (4, 4, 2),
    (4, 5, 1),
    (5, 2, 3),
    (5, 3, 2),
    (5, 4, 1),
)


def optimize_lineup(candidates: list[LineupCandidate]) -> LineupResult:
    """Return the highest-next-GW-xPts legal XI and deterministic bench order."""

    _validate_squad(candidates)
    by_position = {
        position: sorted(
            (player for player in candidates if player.position == position),
            key=_selection_key,
            reverse=True,
        )
        for position in POSITION_LIMITS
    }
    best: tuple[float, tuple[int, int, int], list[LineupCandidate]] | None = None
    for defenders, midfielders, forwards in LEGAL_FORMATIONS:
        starters = (
            by_position["GK"][:1]
            + by_position["DEF"][:defenders]
            + by_position["MID"][:midfielders]
            + by_position["FWD"][:forwards]
        )
        total = sum(player.next_gw_xpts for player in starters)
        candidate = (total, (defenders, midfielders, forwards), starters)
        if best is None or _formation_key(candidate) > _formation_key(best):
            best = candidate
    if best is None:
        raise RuntimeError("No legal starting formation is available")
    base_xpts, formation_parts, selected = best
    starter_ids = {player.player_id for player in selected}
    outfield_bench = sorted(
        (
            player
            for player in candidates
            if player.player_id not in starter_ids and player.position != "GK"
        ),
        key=_selection_key,
        reverse=True,
    )
    goalkeeper_bench = [
        player
        for player in candidates
        if player.player_id not in starter_ids and player.position == "GK"
    ]
    bench_candidates = outfield_bench + goalkeeper_bench
    expected_captain = max(selected, key=_selection_key)
    vice = max(
        (player for player in selected if player.player_id != expected_captain.player_id),
        key=_vice_key,
    )
    options = _captain_options(selected)
    lineup_starters = tuple(
        _lineup_player(
            player,
            "Captain"
            if player.player_id == expected_captain.player_id
            else "Vice captain"
            if player.player_id == vice.player_id
            else "Starter",
            None,
        )
        for player in selected
    )
    bench = tuple(
        _lineup_player(player, "Bench", order)
        for order, player in enumerate(bench_candidates, start=1)
    )
    return LineupResult(
        formation="-".join(map(str, formation_parts)),
        starters=lineup_starters,
        bench=bench,
        captain_id=expected_captain.player_id,
        vice_captain_id=vice.player_id,
        base_xpts=base_xpts,
        projected_points=base_xpts + expected_captain.next_gw_xpts,
        next_3_squad_xpts=sum(player.next_3_xpts for player in candidates),
        next_5_squad_xpts=sum(player.next_5_xpts for player in candidates),
        captain_options=options,
    )


def validate_lineup(result: LineupResult) -> None:
    """Independently validate formation, roles, and bench completeness."""

    if len(result.starters) != 11 or len(result.bench) != 4:
        raise ValueError("A lineup must have 11 starters and four bench players")
    positions = Counter(player.position for player in result.starters)
    if positions["GK"] != 1:
        raise ValueError("A starting XI must contain exactly one goalkeeper")
    if not 3 <= positions["DEF"] <= 5:
        raise ValueError("A starting XI must contain three to five defenders")
    if not 2 <= positions["MID"] <= 5:
        raise ValueError("A starting XI must contain two to five midfielders")
    if not 1 <= positions["FWD"] <= 3:
        raise ValueError("A starting XI must contain one to three forwards")
    ids = {player.player_id for player in result.starters + result.bench}
    if len(ids) != 15:
        raise ValueError("Lineup assignments must contain 15 unique players")
    starter_ids = {player.player_id for player in result.starters}
    if result.captain_id not in starter_ids or result.vice_captain_id not in starter_ids:
        raise ValueError("Captain and vice captain must both start")
    if result.captain_id == result.vice_captain_id:
        raise ValueError("Captain and vice captain must be different players")


def _captain_options(starters: list[LineupCandidate]) -> tuple[CaptainOption, ...]:
    expected = max(starters, key=_selection_key)
    safest = max(starters, key=_safe_captain_key)
    ceiling = max(starters, key=_ceiling_key)
    differential = max(starters, key=_differential_key)
    return (
        CaptainOption(
            "Best expected",
            expected.player_id,
            expected.player,
            expected.next_gw_xpts,
            "Highest blended expected points in the legal starting XI.",
        ),
        CaptainOption(
            "Safest",
            safest.player_id,
            safest.player,
            _safe_captain_key(safest)[0],
            "Balances expected points with expected minutes and downside risk.",
        ),
        CaptainOption(
            "Highest ceiling",
            ceiling.player_id,
            ceiling.player,
            _ceiling_key(ceiling)[0],
            "Uses expected points plus the attacking-return component as a ceiling proxy.",
        ),
        CaptainOption(
            "Best differential",
            differential.player_id,
            differential.player,
            _differential_key(differential)[0],
            "Rewards expected points that are less represented by current ownership.",
        ),
    )


def _validate_squad(candidates: list[LineupCandidate]) -> None:
    if len(candidates) != 15:
        raise ValueError("Current squad must contain exactly 15 players")
    if len({player.player_id for player in candidates}) != 15:
        raise ValueError("Current squad contains duplicate players")
    positions = Counter(player.position for player in candidates)
    if positions != Counter(POSITION_LIMITS):
        raise ValueError("Current squad must have 2 GK, 5 DEF, 5 MID, and 3 FWD")


def _selection_key(player: LineupCandidate) -> tuple[float, float, float, int]:
    return (
        player.next_gw_xpts,
        player.expected_minutes,
        -player.risk,
        -player.player_id,
    )


def _vice_key(player: LineupCandidate) -> tuple[float, float, float, int]:
    availability = min(max(player.expected_minutes / 90.0, 0.0), 1.0)
    return (
        player.next_gw_xpts * availability,
        player.next_gw_xpts,
        -player.risk,
        -player.player_id,
    )


def _safe_captain_key(player: LineupCandidate) -> tuple[float, float, int]:
    availability = min(max(player.expected_minutes / 90.0, 0.0), 1.0)
    score = player.next_gw_xpts * availability * (1.0 - player.risk / 100.0)
    return score, player.next_gw_xpts, -player.player_id


def _ceiling_key(player: LineupCandidate) -> tuple[float, float, int]:
    return (
        player.next_gw_xpts + player.attacking_xpts,
        player.next_gw_xpts,
        -player.player_id,
    )


def _differential_key(player: LineupCandidate) -> tuple[float, float, int]:
    return (
        player.next_gw_xpts * max(0.0, 1.0 - player.ownership / 100.0),
        player.next_gw_xpts,
        -player.player_id,
    )


def _formation_key(
    candidate: tuple[float, tuple[int, int, int], list[LineupCandidate]],
) -> tuple[float, tuple[int, ...], tuple[int, int, int]]:
    total, formation, players = candidate
    ids = tuple(sorted((-player.player_id for player in players), reverse=True))
    return total, ids, formation


def _lineup_player(
    player: LineupCandidate, role: str, bench_order: int | None
) -> LineupPlayer:
    return LineupPlayer(
        player_id=player.player_id,
        player=player.player,
        position=player.position,
        team=player.team,
        opponent=player.opponent,
        current_price=player.current_price,
        expected_minutes=player.expected_minutes,
        next_gw_xpts=player.next_gw_xpts,
        ownership=player.ownership,
        risk=player.risk,
        role=role,
        bench_order=bench_order,
    )
