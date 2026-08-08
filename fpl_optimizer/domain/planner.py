"""Framework-independent multi-Gameweek planning records."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlanningCandidate:
    """One player with static transfer data and per-Gameweek forecasts."""

    player_id: int
    player: str
    position: str
    team: str
    buy_price: float
    selling_price: float
    optimization_score: float
    is_current: bool
    gameweek_xpts: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class PlannedTransfer:
    """One transfer scheduled in a future Gameweek."""

    out_player_id: int
    out_player: str
    out_team: str
    selling_price: float
    in_player_id: int
    in_player: str
    in_team: str
    buy_price: float
    position: str
    bank_change: float


@dataclass(frozen=True, slots=True)
class PlannedGameweek:
    """One step of an optimized multi-period path."""

    gameweek_id: int
    gameweek: str
    transfers: tuple[PlannedTransfer, ...]
    free_transfers_before: int
    free_transfers_after: int
    hit_cost: int
    bank_after: float
    formation: str
    captain_id: int
    captain: str
    starter_ids: tuple[int, ...]
    squad_ids: tuple[int, ...]
    lineup_xpts: float
    captain_xpts: float
    projected_points: float
    net_projected_points: float


@dataclass(frozen=True, slots=True)
class MultiGameweekPlan:
    """Complete jointly optimized transfer and lineup plan."""

    status: str
    solver: str
    horizon: int
    starting_bank: float
    starting_free_transfers: int
    total_transfers: int
    total_hits: int
    gross_projected_points: float
    net_projected_points: float
    weeks: tuple[PlannedGameweek, ...]

