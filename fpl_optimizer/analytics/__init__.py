"""Reusable player analytics records, filters, comparison, and metric metadata."""

from fpl_optimizer.analytics.comparison import (
    UNIVERSE_OPTIONS,
    ComparisonUniverse,
    PlayerRadarProfile,
    RadarMetricValue,
    available_radar_metrics,
    comparison_rows,
    default_radar_metrics,
    radar_profiles,
)
from fpl_optimizer.analytics.filters import PlayerFilterSpec, filter_players
from fpl_optimizer.analytics.forecast_comparison import (
    FORECAST_HORIZONS,
    ForecastComparison,
    ForecastPoint,
    ForecastSeries,
    build_forecast_comparison,
    fixture_comparison_rows,
    forecast_export_rows,
)
from fpl_optimizer.analytics.matrix import (
    MATRIX_PRESETS,
    REFERENCE_METHODS,
    MatrixAnalysis,
    MatrixPoint,
    MatrixPreset,
    QuadrantInsight,
    QuadrantLabels,
    ReferenceMethod,
    available_matrix_metrics,
    available_matrix_presets,
    build_matrix,
)
from fpl_optimizer.analytics.metrics import METRICS, MetricDefinition, metric_definition
from fpl_optimizer.analytics.player_dataset import PlayerAnalyticsRecord, build_player_dataset

__all__ = [
    "METRICS",
    "MATRIX_PRESETS",
    "REFERENCE_METHODS",
    "UNIVERSE_OPTIONS",
    "ComparisonUniverse",
    "FORECAST_HORIZONS",
    "ForecastComparison",
    "ForecastPoint",
    "ForecastSeries",
    "MetricDefinition",
    "MatrixAnalysis",
    "MatrixPoint",
    "MatrixPreset",
    "PlayerAnalyticsRecord",
    "PlayerFilterSpec",
    "PlayerRadarProfile",
    "RadarMetricValue",
    "QuadrantInsight",
    "QuadrantLabels",
    "ReferenceMethod",
    "available_matrix_metrics",
    "available_matrix_presets",
    "available_radar_metrics",
    "build_player_dataset",
    "build_forecast_comparison",
    "build_matrix",
    "comparison_rows",
    "default_radar_metrics",
    "filter_players",
    "fixture_comparison_rows",
    "forecast_export_rows",
    "metric_definition",
    "radar_profiles",
]
