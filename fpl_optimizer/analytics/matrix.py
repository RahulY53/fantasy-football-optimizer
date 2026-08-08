"""Raw-metric 2×2 player matrix calculations and preset definitions."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median
from typing import Literal

from fpl_optimizer.analytics.metrics import METRICS, MetricDefinition, metric_definition
from fpl_optimizer.analytics.player_dataset import PlayerAnalyticsRecord

ReferenceMethod = Literal["Median", "Mean", "Position Median", "Custom"]
QuadrantKey = Literal["upper_left", "upper_right", "lower_left", "lower_right"]

REFERENCE_METHODS: tuple[ReferenceMethod, ...] = (
    "Median",
    "Mean",
    "Position Median",
    "Custom",
)


@dataclass(frozen=True, slots=True)
class QuadrantLabels:
    """Human-readable interpretations for the four matrix quadrants."""

    upper_left: str
    upper_right: str
    lower_left: str
    lower_right: str

    def label(self, key: QuadrantKey) -> str:
        if key == "upper_left":
            return self.upper_left
        if key == "upper_right":
            return self.upper_right
        if key == "lower_left":
            return self.lower_left
        return self.lower_right


@dataclass(frozen=True, slots=True)
class MatrixPreset:
    """One useful predefined matrix view."""

    key: str
    label: str
    description: str
    x_metric: str
    y_metric: str
    quadrant_labels: QuadrantLabels
    diagonal: bool = False


@dataclass(frozen=True, slots=True)
class MatrixPoint:
    """One plotted player with raw values and hover context."""

    player_id: int
    full_name: str
    team: str
    position: str
    price: float
    ownership: float
    expected_minutes: float | None
    blended_xpts: float | None
    risk: float | None
    optimization_score: float | None
    x_value: float
    y_value: float
    x_formatted: str
    y_formatted: str
    quadrant: QuadrantKey


@dataclass(frozen=True, slots=True)
class QuadrantInsight:
    """Ranked players assigned to one quadrant."""

    key: QuadrantKey
    label: str
    players: tuple[MatrixPoint, ...]


@dataclass(frozen=True, slots=True)
class MatrixAnalysis:
    """Complete raw-axis matrix result consumed by Plotly and insight cards."""

    x_metric: MetricDefinition
    y_metric: MetricDefinition
    x_reference: float
    y_reference: float
    reference_method: ReferenceMethod
    reference_position: str | None
    points: tuple[MatrixPoint, ...]
    labels: QuadrantLabels
    insights: tuple[QuadrantInsight, ...]
    diagonal: bool


MATRIX_PRESETS: dict[str, MatrixPreset] = {
    preset.key: preset
    for preset in (
        MatrixPreset(
            "value_map",
            "Value Map",
            "Find stronger five-Gameweek returns at lower prices.",
            "price",
            "xpts_5gw",
            QuadrantLabels(
                "HIGH RETURN / LOWER PRICE",
                "HIGH RETURN / HIGHER PRICE",
                "LOW RETURN / LOWER PRICE",
                "LOW RETURN / HIGHER PRICE",
            ),
        ),
        MatrixPreset(
            "attacking_threat",
            "Attacking Threat",
            "Separate projected scorers, creators, and dual threats.",
            "goal_xpts",
            "assist_xpts",
            QuadrantLabels(
                "CREATOR / LOWER GOAL THREAT",
                "DUAL ATTACKING THREAT",
                "LOWER ATTACKING THREAT",
                "SCORER / LOWER ASSIST THREAT",
            ),
        ),
        MatrixPreset(
            "reliability_upside",
            "Reliability vs Forecast Upside",
            "Find high five-Gameweek forecasts with lower modeled risk.",
            "risk",
            "xpts_5gw",
            QuadrantLabels(
                "HIGH UPSIDE / LOW RISK",
                "HIGH UPSIDE / HIGH RISK",
                "LOW UPSIDE / LOW RISK",
                "LOW UPSIDE / HIGH RISK",
            ),
        ),
        MatrixPreset(
            "minutes_output",
            "Minutes vs Output",
            "Contrast expected opportunity with forecast production per 90 minutes.",
            "expected_minutes",
            "xpts_per_90",
            QuadrantLabels(
                "PRODUCTIVE / LOWER MINUTES",
                "PRODUCTIVE / HIGH MINUTES",
                "LOW OUTPUT / LOWER MINUTES",
                "LOW OUTPUT / HIGH MINUTES",
            ),
        ),
        MatrixPreset(
            "ownership_expectation",
            "Ownership vs Expectation",
            "Identify lower-owned players with strong five-Gameweek forecasts.",
            "ownership",
            "xpts_5gw",
            QuadrantLabels(
                "HIGH EXPECTATION / DIFFERENTIAL",
                "HIGH EXPECTATION / HIGH OWNERSHIP",
                "LOW EXPECTATION / DIFFERENTIAL",
                "LOW EXPECTATION / HIGH OWNERSHIP",
            ),
        ),
        MatrixPreset(
            "market_model",
            "Market vs Model",
            "Compare next-Gameweek statistical and market forecasts on identical units.",
            "stat_xpts",
            "market_xpts",
            QuadrantLabels(
                "MARKET HIGH / MODEL LOW",
                "BOTH FORECASTS HIGH",
                "BOTH FORECASTS LOW",
                "MODEL HIGH / MARKET LOW",
            ),
            diagonal=True,
        ),
        MatrixPreset(
            "market_disagreement",
            "Market Disagreement",
            "Surface players where market xPts differs materially from the statistical model.",
            "stat_xpts",
            "market_edge",
            QuadrantLabels(
                "MARKET BULLISH / MODEL LOW",
                "MARKET BULLISH / MODEL HIGH",
                "MARKET BEARISH / MODEL LOW",
                "MARKET BEARISH / MODEL HIGH",
            ),
        ),
    )
}


def available_matrix_metrics(
    records: tuple[PlayerAnalyticsRecord, ...],
) -> tuple[str, ...]:
    """Return registered metrics with at least one raw value in the plotted population."""

    return tuple(
        key for key in METRICS if any(record.metric(key) is not None for record in records)
    )


def available_matrix_presets(
    records: tuple[PlayerAnalyticsRecord, ...],
) -> tuple[MatrixPreset, ...]:
    """Return only presets whose two axes have data in the current population."""

    available = set(available_matrix_metrics(records))
    return tuple(
        preset
        for preset in MATRIX_PRESETS.values()
        if preset.x_metric in available and preset.y_metric in available
    )


def build_matrix(
    records: tuple[PlayerAnalyticsRecord, ...],
    x_key: str,
    y_key: str,
    reference_method: ReferenceMethod = "Median",
    *,
    custom_x: float | None = None,
    custom_y: float | None = None,
    reference_position: str | None = None,
    labels: QuadrantLabels | None = None,
    diagonal: bool = False,
) -> MatrixAnalysis:
    """Build one raw-axis matrix without normalizing or recalculating forecasts."""

    if x_key == y_key:
        raise ValueError("Choose different metrics for the X and Y axes")
    x_definition = metric_definition(x_key)
    y_definition = metric_definition(y_key)
    plotted = [
        (record, x_value, y_value)
        for record in records
        if (x_value := record.metric(x_key)) is not None
        and (y_value := record.metric(y_key)) is not None
    ]
    if not plotted:
        raise ValueError("No players have values for both selected metrics")

    x_reference = _reference(
        plotted,
        1,
        reference_method,
        custom_x,
        reference_position,
    )
    y_reference = _reference(
        plotted,
        2,
        reference_method,
        custom_y,
        reference_position,
    )
    resolved_labels = labels or _generic_labels(x_definition, y_definition)

    points = tuple(
        MatrixPoint(
            player_id=record.player_id,
            full_name=record.full_name,
            team=record.team,
            position=record.position,
            price=record.price,
            ownership=record.ownership,
            expected_minutes=record.expected_minutes,
            blended_xpts=record.blended_xpts,
            risk=record.risk,
            optimization_score=record.optimization_score,
            x_value=x_value,
            y_value=y_value,
            x_formatted=x_definition.format_value(x_value),
            y_formatted=y_definition.format_value(y_value),
            quadrant=_quadrant(x_value, y_value, x_reference, y_reference),
        )
        for record, x_value, y_value in plotted
    )
    quadrant_order: tuple[QuadrantKey, ...] = (
        "upper_left",
        "upper_right",
        "lower_left",
        "lower_right",
    )
    insights = tuple(
        QuadrantInsight(
            key=key,
            label=resolved_labels.label(key),
            players=tuple(
                sorted(
                    (point for point in points if point.quadrant == key),
                    key=_insight_rank,
                    reverse=True,
                )
            ),
        )
        for key in quadrant_order
    )
    return MatrixAnalysis(
        x_metric=x_definition,
        y_metric=y_definition,
        x_reference=x_reference,
        y_reference=y_reference,
        reference_method=reference_method,
        reference_position=reference_position,
        points=points,
        labels=resolved_labels,
        insights=insights,
        diagonal=diagonal,
    )


def _reference(
    plotted: list[tuple[PlayerAnalyticsRecord, float, float]],
    value_index: Literal[1, 2],
    method: ReferenceMethod,
    custom_value: float | None,
    position: str | None,
) -> float:
    if method == "Custom":
        if custom_value is None:
            raise ValueError("Custom reference values are required")
        return custom_value
    population = plotted
    if method == "Position Median":
        if position is None:
            raise ValueError("Choose a position for Position Median")
        population = [row for row in plotted if row[0].position == position]
        if not population:
            raise ValueError(f"No plotted players are available at position {position}")
    values = [row[1] if value_index == 1 else row[2] for row in population]
    return mean(values) if method == "Mean" else median(values)


def _quadrant(
    x_value: float,
    y_value: float,
    x_reference: float,
    y_reference: float,
) -> QuadrantKey:
    if y_value >= y_reference:
        return "upper_right" if x_value >= x_reference else "upper_left"
    return "lower_right" if x_value >= x_reference else "lower_left"


def _generic_labels(
    x_definition: MetricDefinition,
    y_definition: MetricDefinition,
) -> QuadrantLabels:
    high_y = f"HIGH {y_definition.label.upper()}"
    low_y = f"LOW {y_definition.label.upper()}"
    low_x = f"LOW {x_definition.label.upper()}"
    high_x = f"HIGH {x_definition.label.upper()}"
    return QuadrantLabels(
        f"{high_y} / {low_x}",
        f"{high_y} / {high_x}",
        f"{low_y} / {low_x}",
        f"{low_y} / {high_x}",
    )


def _insight_rank(point: MatrixPoint) -> tuple[int, float, float]:
    return (
        int(point.optimization_score is not None),
        point.optimization_score or 0.0,
        point.y_value,
    )
