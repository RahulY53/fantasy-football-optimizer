"""Framework-independent player comparison and radar normalization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fpl_optimizer.analytics.metrics import METRICS, metric_definition
from fpl_optimizer.analytics.player_dataset import PlayerAnalyticsRecord
from fpl_optimizer.scoring.normalization import percentile_scores

ComparisonUniverse = Literal["All Players", "Same Position", "Selected Players"]

UNIVERSE_OPTIONS: tuple[ComparisonUniverse, ...] = (
    "All Players",
    "Same Position",
    "Selected Players",
)

GENERIC_RADAR_METRICS = (
    "blended_xpts",
    "expected_minutes",
    "xpts_5gw",
    "value",
    "risk",
    "form",
    "optimization_score",
)

POSITION_RADAR_METRICS: dict[str, tuple[str, ...]] = {
    "GK": (
        "blended_xpts",
        "expected_minutes",
        "start_probability",
        "clean_sheet_xpts",
        "save_xpts",
        "bonus_xpts",
        "xpts_5gw",
        "value",
        "risk",
    ),
    "DEF": (
        "blended_xpts",
        "expected_minutes",
        "start_probability",
        "clean_sheet_xpts",
        "attacking_xpts",
        "xpts_5gw",
        "value",
        "risk",
    ),
    "MID": (
        "blended_xpts",
        "expected_minutes",
        "start_probability",
        "goal_xpts",
        "assist_xpts",
        "xpts_5gw",
        "value",
        "risk",
    ),
    "FWD": (
        "blended_xpts",
        "expected_minutes",
        "start_probability",
        "goal_xpts",
        "assist_xpts",
        "xpts_5gw",
        "value",
        "risk",
    ),
}


@dataclass(frozen=True, slots=True)
class RadarMetricValue:
    """One player's raw and normalized value for a radar dimension."""

    key: str
    label: str
    raw_value: float
    formatted_value: str
    score: float


@dataclass(frozen=True, slots=True)
class PlayerRadarProfile:
    """All radar dimensions for one selected player."""

    player_id: int
    full_name: str
    team: str
    position: str
    metrics: tuple[RadarMetricValue, ...]


def available_radar_metrics(
    selected: tuple[PlayerAnalyticsRecord, ...],
) -> tuple[str, ...]:
    """Return registry metrics supported by every selected player and position."""

    positions = {record.position for record in selected}
    return tuple(
        key
        for key, definition in METRICS.items()
        if all(record.metric(key) is not None for record in selected)
        and positions.issubset(definition.supports_positions)
    )


def default_radar_metrics(
    selected: tuple[PlayerAnalyticsRecord, ...],
    maximum: int = 8,
) -> tuple[str, ...]:
    """Choose position-aware defaults, falling back to generic available metrics."""

    if not selected:
        return ()
    available = available_radar_metrics(selected)
    available_set = set(available)
    positions = {record.position for record in selected}
    preferred = (
        POSITION_RADAR_METRICS[next(iter(positions))]
        if len(positions) == 1
        else GENERIC_RADAR_METRICS
    )
    result = [key for key in preferred if key in available_set]
    for key in available:
        if key not in result:
            result.append(key)
    return tuple(result[:maximum])


def radar_profiles(
    selected: tuple[PlayerAnalyticsRecord, ...],
    all_records: tuple[PlayerAnalyticsRecord, ...],
    metric_keys: tuple[str, ...],
    universe: ComparisonUniverse,
) -> tuple[PlayerRadarProfile, ...]:
    """Normalize selected players against the requested comparison universe."""

    if not 2 <= len(selected) <= 5:
        raise ValueError("Select between two and five players")
    if not 3 <= len(metric_keys) <= 10:
        raise ValueError("Choose between three and ten radar metrics")
    if len(set(metric_keys)) != len(metric_keys):
        raise ValueError("Radar metrics must be unique")
    selected_positions = {record.position for record in selected}
    if universe == "Same Position" and len(selected_positions) != 1:
        raise ValueError("Same Position is available only when every selected player matches")

    comparison_records = _comparison_records(selected, all_records, universe)
    normalized: dict[tuple[int, str], float] = {}
    for key in metric_keys:
        definition = metric_definition(key)
        if not selected_positions.issubset(definition.supports_positions):
            raise ValueError(f"{definition.label} does not support every selected position")
        if any(record.metric(key) is None for record in selected):
            raise ValueError(f"{definition.label} is unavailable for a selected player")
        available = [
            (record.player_id, value)
            for record in comparison_records
            if (value := record.metric(key)) is not None
        ]
        percentiles = percentile_scores([value for _, value in available])
        for (player_id, _), percentile in zip(available, percentiles, strict=True):
            normalized[player_id, key] = (
                percentile if definition.higher_is_better else 100.0 - percentile
            )

    profiles: list[PlayerRadarProfile] = []
    for record in selected:
        values: list[RadarMetricValue] = []
        for key in metric_keys:
            definition = metric_definition(key)
            raw_value = record.metric(key)
            if raw_value is None:  # Protected by validation above; keeps type narrowing explicit.
                raise ValueError(f"{definition.label} is unavailable for {record.full_name}")
            values.append(
                RadarMetricValue(
                    key=key,
                    label=definition.comparison_label,
                    raw_value=raw_value,
                    formatted_value=definition.format_value(raw_value),
                    score=normalized[record.player_id, key],
                )
            )
        profiles.append(
            PlayerRadarProfile(
                player_id=record.player_id,
                full_name=record.full_name,
                team=record.team,
                position=record.position,
                metrics=tuple(values),
            )
        )
    return tuple(profiles)


def comparison_rows(
    selected: tuple[PlayerAnalyticsRecord, ...],
) -> list[dict[str, object]]:
    """Return a stable raw-metric table for the Compare view."""

    columns = {
        "Full Name": "full_name",
        "Team": "team",
        "Position": "position",
        "Price": "price",
        "Ownership %": "ownership",
        "Expected minutes": "expected_minutes",
        "Start probability %": "start_probability",
        "Goal probability %": "goal_probability",
        "Goal xPts": "goal_xpts",
        "Assist xPts": "assist_xpts",
        "Clean sheet xPts": "clean_sheet_xpts",
        "Save xPts": "save_xpts",
        "Bonus xPts": "bonus_xpts",
        "Stat xPts": "stat_xpts",
        "Market xPts": "market_xpts",
        "Blended xPts": "blended_xpts",
        "3GW xPts": "xpts_3gw",
        "5GW xPts": "xpts_5gw",
        "Value": "value",
        "Risk": "risk",
        "Optimization Score": "optimization_score",
    }
    return [
        {label: getattr(record, attribute) for label, attribute in columns.items()}
        for record in selected
    ]


def _comparison_records(
    selected: tuple[PlayerAnalyticsRecord, ...],
    all_records: tuple[PlayerAnalyticsRecord, ...],
    universe: ComparisonUniverse,
) -> tuple[PlayerAnalyticsRecord, ...]:
    if universe == "Selected Players":
        return selected
    if universe == "Same Position":
        position = selected[0].position
        return tuple(record for record in all_records if record.position == position)
    if universe == "All Players":
        return all_records
    raise ValueError(f"Unknown comparison universe: {universe}")
