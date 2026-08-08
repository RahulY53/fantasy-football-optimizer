"""Framework-independent chip evaluation records."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChipCandidate:
    """One player available to a chip squad optimizer."""

    player_id: int
    player: str
    position: str
    team: str
    price: float
    optimization_score: float
    gameweek_xpts: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class ChipWeekPlan:
    """One chip scenario's squad and lineup in a Gameweek."""

    gameweek_id: int
    gameweek: str
    squad_ids: tuple[int, ...]
    starter_ids: tuple[int, ...]
    captain_id: int
    captain: str
    formation: str
    projected_points: float


@dataclass(frozen=True, slots=True)
class ChipOpportunity:
    """Best modeled use of one chip inside the selected horizon."""

    chip: str
    available: bool
    recommended_gameweek: str | None
    projected_gain: float
    rationale: str
    players_in: tuple[int, ...]
    players_out: tuple[int, ...]
    weeks: tuple[ChipWeekPlan, ...]


@dataclass(frozen=True, slots=True)
class ChipEvaluation:
    """Comparison of all four FPL chip opportunities."""

    horizon: int
    budget: float
    current_projected_points: float
    best_chip: str | None
    best_gain: float
    opportunities: tuple[ChipOpportunity, ...]

