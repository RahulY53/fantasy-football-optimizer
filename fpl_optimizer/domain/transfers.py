"""Framework-independent transfer optimization records."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TransferCandidate:
    """One player available to the transfer optimizer."""

    player_id: int
    player: str
    position: str
    team: str
    buy_price: float
    selling_price: float | None
    horizon_xpts: float
    optimization_score: float
    is_current: bool


@dataclass(frozen=True, slots=True)
class TransferMove:
    """One paired player sale and purchase."""

    out_player_id: int
    out_player: str
    out_team: str
    selling_price: float
    in_player_id: int
    in_player: str
    in_team: str
    buy_price: float
    position: str
    budget_change: float
    horizon_xpts_gain: float


@dataclass(frozen=True, slots=True)
class TransferPlanResult:
    """One exact transfer-count alternative."""

    transfers: int
    moves: tuple[TransferMove, ...]
    final_player_ids: tuple[int, ...]
    final_squad_xpts: float
    gross_gain: float
    hit_cost: int
    net_gain: float
    ending_bank: float


@dataclass(frozen=True, slots=True)
class TransferEvaluation:
    """Compared roll, one-transfer, and two-transfer plans."""

    recommendation: str
    recommended_transfers: int
    rationale: str
    horizon: int
    free_transfers: int
    starting_bank: float
    roll_flexibility_value: float
    current_squad_xpts: float
    plans: tuple[TransferPlanResult, ...]
