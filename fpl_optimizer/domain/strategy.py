"""Framework-independent user strategy and scoring records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

StrategyMode = Literal["simple", "advanced"]


@dataclass(frozen=True, slots=True)
class StrategyProfile:
    """User preferences applied after forecasting."""

    name: str
    mode: StrategyMode
    preset: str
    horizon: int
    risk_appetite: int
    transfer_reluctance: int
    ownership_preference: int
    weights: dict[str, int]


@dataclass(frozen=True, slots=True)
class PlayerStrategyInput:
    """Raw, unnormalized player features used by the strategy layer."""

    player_id: int
    player: str
    position: str
    team: str
    price: float
    ownership: float
    form: float
    status: str
    chance_next_round: int | None
    horizon_xpts: float
    week_xpts: tuple[float, ...]
    expected_minutes: float
    fixture_quality: float
    attacking_xpts: float
    clean_sheet_xpts: float
    bonus_xpts: float
    confidence: float


@dataclass(frozen=True, slots=True)
class ScoreContribution:
    """One normalized feature's contribution to a player score."""

    feature: str
    label: str
    raw_value: float
    percentile: float
    raw_weight: float
    normalized_weight: float
    contribution: float


@dataclass(frozen=True, slots=True)
class PlayerStrategyScore:
    """Explainable user-preference score for one player."""

    player_id: int
    player: str
    position: str
    team: str
    price: float
    ownership: float
    horizon_xpts: float
    value: float
    risk: float
    score: float
    contributions: tuple[ScoreContribution, ...]
