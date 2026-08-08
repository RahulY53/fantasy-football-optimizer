"""Central registry for player analytics metrics and chart semantics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    """Describe one raw analytical metric consistently across every presentation."""

    key: str
    label: str
    description: str
    unit: str
    format: str
    higher_is_better: bool
    supports_positions: tuple[str, ...] = ("GK", "DEF", "MID", "FWD")
    normalization_method: str = "percentile"
    radar_label: str | None = None


METRICS: dict[str, MetricDefinition] = {
    item.key: item
    for item in (
        MetricDefinition("price", "Price", "Current FPL purchase price.", "£m", "£%.1fm", False),
        MetricDefinition(
            "ownership",
            "Ownership",
            "Share of FPL teams selecting the player.",
            "%",
            "%.1f%%",
            False,
        ),
        MetricDefinition(
            "expected_minutes",
            "Expected Minutes",
            "Projected minutes in the next Gameweek.",
            "minutes",
            "%.0f",
            True,
        ),
        MetricDefinition(
            "stat_xpts",
            "Statistical xPts",
            "Next-Gameweek statistical forecast.",
            "pts",
            "%.1f",
            True,
        ),
        MetricDefinition(
            "market_xpts",
            "Market xPts",
            "Next-Gameweek bookmaker-derived forecast.",
            "pts",
            "%.1f",
            True,
        ),
        MetricDefinition(
            "blended_xpts",
            "Blended xPts",
            "Next-Gameweek statistical and market blend.",
            "pts",
            "%.1f",
            True,
        ),
        MetricDefinition(
            "xpts_3gw", "3GW xPts", "Expected points over three Gameweeks.", "pts", "%.1f", True
        ),
        MetricDefinition(
            "xpts_5gw", "5GW xPts", "Expected points over five Gameweeks.", "pts", "%.1f", True
        ),
        MetricDefinition(
            "xpts_6gw", "6GW xPts", "Expected points over six Gameweeks.", "pts", "%.1f", True
        ),
        MetricDefinition(
            "value", "Value", "Forecast value relative to price.", "score", "%.1f", True
        ),
        MetricDefinition(
            "risk",
            "Risk",
            "Combined availability and rotation risk.",
            "score",
            "%.0f/100",
            False,
            radar_label="Reliability",
        ),
        MetricDefinition(
            "optimization_score",
            "Optimization Score",
            "Current strategy-adjusted player score.",
            "score",
            "%.1f",
            True,
        ),
        MetricDefinition(
            "total_points", "Points", "Current-season FPL points.", "pts", "%.0f", True
        ),
        MetricDefinition("form", "Form", "Official FPL form measure.", "score", "%.1f", True),
        MetricDefinition(
            "points_per_game",
            "Points per Game",
            "Current-season FPL points per match.",
            "pts",
            "%.1f",
            True,
        ),
    )
}


def metric_definition(key: str) -> MetricDefinition:
    """Return one registered metric or raise a useful error."""

    try:
        return METRICS[key]
    except KeyError as error:
        raise KeyError(f"Unknown analytics metric: {key}") from error
