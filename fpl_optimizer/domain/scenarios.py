"""Framework-independent records for advanced what-if analysis."""

from __future__ import annotations

from dataclasses import dataclass

from fpl_optimizer.domain.chips import ChipOpportunity
from fpl_optimizer.domain.transfers import TransferEvaluation


@dataclass(frozen=True, slots=True)
class ScenarioAssumptions:
    """Session-only changes applied to cached forecast inputs."""

    start_player_id: int | None = None
    start_probability: float | None = None
    unavailable_player_ids: tuple[int, ...] = ()
    attack_team: str | None = None
    attack_change: float = 0.0
    protected_player_ids: tuple[int, ...] = ()
    must_sell_player_ids: tuple[int, ...] = ()
    must_buy_player_ids: tuple[int, ...] = ()
    excluded_player_ids: tuple[int, ...] = ()
    forced_chip: str | None = None
    forced_gameweek_id: int | None = None


@dataclass(frozen=True, slots=True)
class ScenarioPlayerChoice:
    """Selectable player metadata for scenario controls."""

    player_id: int
    player: str
    team: str
    position: str
    is_current: bool


@dataclass(frozen=True, slots=True)
class WhatIfContext:
    """Current data available for building a valid scenario."""

    players: tuple[ScenarioPlayerChoice, ...]
    teams: tuple[str, ...]
    gameweeks: tuple[tuple[int, str], ...]
    available_chips: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScenarioPlayerImpact:
    """One player's forecast movement caused by assumptions."""

    player_id: int
    player: str
    team: str
    baseline_xpts: float
    scenario_xpts: float
    change: float


@dataclass(frozen=True, slots=True)
class WhatIfReport:
    """Baseline and scenario decision outputs for direct comparison."""

    assumptions: tuple[str, ...]
    baseline_transfers: TransferEvaluation
    scenario_transfers: TransferEvaluation
    baseline_chip: ChipOpportunity | None
    scenario_chip: ChipOpportunity | None
    impacts: tuple[ScenarioPlayerImpact, ...]

