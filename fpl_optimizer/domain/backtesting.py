"""Framework-independent records for historical forecast evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class HistoricalOutcomeInput:
    """One validated official-player/Gameweek result ready for persistence."""

    player_fpl_id: int
    gameweek_fpl_id: int
    actual_points: float
    actual_minutes: int | None = None
    goals: int | None = None
    assists: int | None = None
    clean_sheets: int | None = None
    saves: int | None = None
    bonus: int | None = None
    finalized_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class BacktestObservation:
    """One leakage-safe historical prediction paired with its realized result."""

    player_id: int
    player: str
    position: str
    gameweek_id: int
    gameweek: str
    stat_xpts: float
    market_xpts: float | None
    actual_points: float
    expected_minutes: float
    actual_minutes: int | None
    prediction_at: datetime


@dataclass(frozen=True, slots=True)
class AccuracyMetrics:
    """Standard point-forecast error measurements."""

    samples: int
    mae: float
    rmse: float
    bias: float
    correlation: float | None


@dataclass(frozen=True, slots=True)
class BlendEvaluation:
    """Evaluation-set accuracy for one market blend weight."""

    market_weight: float
    calibration_rmse: float
    metrics: AccuracyMetrics


@dataclass(frozen=True, slots=True)
class PositionEvaluation:
    """Selected-blend accuracy for one FPL position."""

    position: str
    metrics: AccuracyMetrics


@dataclass(frozen=True, slots=True)
class CalibrationBand:
    """Observed versus predicted points within a forecast band."""

    label: str
    samples: int
    mean_prediction: float
    mean_actual: float
    bias: float


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Complete chronological calibration and evaluation report."""

    observations: int
    gameweeks: int
    calibration_gameweeks: tuple[str, ...]
    evaluation_gameweeks: tuple[str, ...]
    evaluation_mode: str
    selected_market_weight: float
    statistical: AccuracyMetrics
    market: AccuracyMetrics | None
    selected_blend: AccuracyMetrics
    expected_minutes: AccuracyMetrics | None
    weights: tuple[BlendEvaluation, ...]
    positions: tuple[PositionEvaluation, ...]
    calibration_bands: tuple[CalibrationBand, ...]
    warnings: tuple[str, ...]
