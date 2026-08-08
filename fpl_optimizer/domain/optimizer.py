"""Framework-independent squad optimization records."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SquadCandidate:
    """One selectable player with a strategy utility and forecast."""

    player_id: int
    player: str
    position: str
    team: str
    price: float
    ownership: float
    horizon_xpts: float
    risk: float
    optimization_score: float


@dataclass(frozen=True, slots=True)
class SquadOptimizationRequest:
    """User constraints for one initial-squad solve."""

    budget: float = 100.0
    locked_player_ids: tuple[int, ...] = ()
    excluded_player_ids: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class SquadPlayer:
    """One selected player in an optimized squad."""

    player_id: int
    player: str
    position: str
    team: str
    price: float
    ownership: float
    horizon_xpts: float
    risk: float
    optimization_score: float
    locked: bool


@dataclass(frozen=True, slots=True)
class SquadOptimizationResult:
    """A complete legal 15-player squad and solver diagnostics."""

    status: str
    solver: str
    players: tuple[SquadPlayer, ...]
    budget: float
    total_cost: float
    budget_remaining: float
    objective_score: float
    total_xpts: float
    average_ownership: float
    average_risk: float
