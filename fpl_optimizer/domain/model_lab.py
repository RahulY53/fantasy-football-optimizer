"""Read-only records for inspecting the forecast and strategy models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ModelVersionSummary:
    """Safe metadata for one immutable statistical model version."""

    name: str
    semantic_version: str
    feature_schema: str
    code_revision: str
    created_at: datetime
    training_cutoff_at: datetime | None
    forecast_rows: int
    parameters: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class PlayerModelDiagnostic:
    """First-horizon cached forecast values used by the lab."""

    player_id: int
    player: str
    team: str
    position: str
    gameweek: str
    opponent: str
    status: str
    expected_minutes: float
    start_probability: float
    confidence: str
    stat_xpts: float
    market_xpts: float | None
    blended_xpts: float
    market_edge: float | None
    model_version: str


@dataclass(frozen=True, slots=True)
class FeatureInfluence:
    """Aggregate contribution of one feature in the active strategy score."""

    feature: str
    label: str
    raw_weight: float
    normalized_weight: float
    mean_contribution: float
    top_player: str
    top_contribution: float


@dataclass(frozen=True, slots=True)
class ModelLabReport:
    """Complete cached diagnostics shown in the advanced Model Lab."""

    generated_at: datetime
    forecast_at: datetime | None
    market_forecast_at: datetime | None
    market_weight: float
    diagnostics: tuple[PlayerModelDiagnostic, ...]
    versions: tuple[ModelVersionSummary, ...]
    feature_influence: tuple[FeatureInfluence, ...]
    recent_backtests: tuple[dict[str, object], ...]
    latest_backtest: dict[str, object] | None
    safe_settings: tuple[tuple[str, str], ...]

