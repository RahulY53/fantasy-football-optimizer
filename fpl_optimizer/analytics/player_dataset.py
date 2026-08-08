"""Build one reusable, presentation-independent player analytics dataset."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import cast

from fpl_optimizer.analytics.metrics import METRICS
from fpl_optimizer.scoring.normalization import percentile_scores


@dataclass(frozen=True, slots=True)
class PlayerAnalyticsRecord:
    """Canonical raw and normalized metrics consumed by tables and charts."""

    player_id: int
    full_name: str
    display_name: str
    web_name: str
    name_search: str
    team: str
    position: str
    price: float
    ownership: float
    status: str
    news: str
    opponent: str | None
    expected_minutes: float | None
    start_probability: float | None
    stat_xpts: float | None
    market_xpts: float | None
    blended_xpts: float | None
    goal_probability: float | None
    goal_xpts: float | None
    assist_xpts: float | None
    clean_sheet_xpts: float | None
    save_xpts: float | None
    bonus_xpts: float | None
    attacking_xpts: float | None
    xpts_3gw: float | None
    xpts_5gw: float | None
    xpts_6gw: float | None
    value: float | None
    risk: float | None
    optimization_score: float | None
    total_points: float
    form: float
    points_per_game: float
    forecast_confidence: str | None
    updated: datetime | None
    details: dict[str, object]
    normalized: dict[str, float | None]

    def metric(self, key: str) -> float | None:
        """Return a registered raw metric by key."""

        if key not in METRICS:
            raise KeyError(f"Unknown analytics metric: {key}")
        return cast(float | None, getattr(self, key))

    def as_row(self) -> dict[str, object]:
        """Return the established UI column names without recalculating metrics."""

        row = dict(self.details)
        row.update(
            {
                "Player ID": self.player_id,
                "Full Name": self.full_name,
                "Player": self.display_name,
                "Web Name": self.web_name,
                "Name Search": self.name_search,
                "Team": self.team,
                "Position": self.position,
                "Price": self.price,
                "Ownership %": self.ownership,
                "Status": self.status,
                "News": self.news,
                "Opponent": self.opponent,
                "Expected minutes": self.expected_minutes,
                "Start probability %": self.start_probability,
                "Stat xPts": self.stat_xpts,
                "Market xPts": self.market_xpts,
                "Blended xPts": self.blended_xpts,
                "Goal probability %": self.goal_probability,
                "Goal xPts": self.goal_xpts,
                "Assist xPts": self.assist_xpts,
                "Clean sheet xPts": self.clean_sheet_xpts,
                "Save xPts": self.save_xpts,
                "Bonus xPts": self.bonus_xpts,
                "Attacking xPts": self.attacking_xpts,
                "3GW xPts": self.xpts_3gw,
                "5GW xPts": self.xpts_5gw,
                "6GW xPts": self.xpts_6gw,
                "Value": self.value,
                "Risk": self.risk,
                "Optimization Score": self.optimization_score,
                "Points": self.total_points,
                "Form": self.form,
                "Points/game": self.points_per_game,
                "Forecast confidence": self.forecast_confidence,
                "Updated": self.updated,
            }
        )
        return row


def build_player_dataset(
    players: list[dict[str, object]],
    forecasts: list[dict[str, object]],
    scores: list[dict[str, object]],
) -> tuple[PlayerAnalyticsRecord, ...]:
    """Join precomputed read models and add cross-player percentile normalizations."""

    forecast_by_id = {_integer(row, "Player ID"): row for row in forecasts}
    score_by_id = {_integer(row, "Player ID"): row for row in scores}
    records: list[PlayerAnalyticsRecord] = []
    for player in players:
        player_id = _integer(player, "Player ID")
        forecast = forecast_by_id.get(player_id, {})
        score = score_by_id.get(player_id, {})
        records.append(
            PlayerAnalyticsRecord(
                player_id=player_id,
                full_name=str(player["Full Name"]),
                display_name=str(player["Display Name"]),
                web_name=str(player["Web Name"]),
                name_search=str(player["Name Search"]),
                team=str(player["Team"]),
                position=str(player["Position"]),
                price=_number(player, "Price") or 0.0,
                ownership=_number(player, "Ownership %") or 0.0,
                status=str(player["Status"]),
                news=str(player["News"]),
                opponent=_text(forecast, "Opponent"),
                expected_minutes=_number(forecast, "Expected minutes"),
                start_probability=_number(forecast, "Start probability %"),
                stat_xpts=_number(forecast, "Stat xPts"),
                market_xpts=_number(forecast, "Market xPts"),
                blended_xpts=_number(forecast, "Blended xPts"),
                goal_probability=_number(forecast, "Goal probability %"),
                goal_xpts=_number(forecast, "Goal xPts"),
                assist_xpts=_number(forecast, "Assist xPts"),
                clean_sheet_xpts=_number(forecast, "Clean sheet xPts"),
                save_xpts=_number(forecast, "Save xPts"),
                bonus_xpts=_number(forecast, "Bonus xPts"),
                attacking_xpts=_number(forecast, "Attacking xPts"),
                xpts_3gw=_number(forecast, "3GW xPts"),
                xpts_5gw=_number(forecast, "5GW xPts"),
                xpts_6gw=_number(forecast, "6GW xPts"),
                value=_number(score, "Value"),
                risk=_number(score, "Risk"),
                optimization_score=_number(score, "Optimization Score"),
                total_points=_number(player, "Points") or 0.0,
                form=_number(player, "Form") or 0.0,
                points_per_game=_number(player, "Points/game") or 0.0,
                forecast_confidence=_text(forecast, "Forecast confidence"),
                updated=cast(datetime | None, player.get("Updated")),
                details=dict(player),
                normalized={},
            )
        )
    return _with_normalized_metrics(records)


def _with_normalized_metrics(
    records: list[PlayerAnalyticsRecord],
) -> tuple[PlayerAnalyticsRecord, ...]:
    normalized: dict[int, dict[str, float | None]] = {
        record.player_id: {key: None for key in METRICS} for record in records
    }
    for key, definition in METRICS.items():
        available: list[tuple[int, float]] = []
        for record in records:
            value = record.metric(key)
            if value is not None:
                available.append((record.player_id, value))
        percentiles = percentile_scores([value for _, value in available])
        for (player_id, _), percentile in zip(available, percentiles, strict=True):
            normalized[player_id][key] = (
                percentile if definition.higher_is_better else 100.0 - percentile
            )
    return tuple(replace(record, normalized=normalized[record.player_id]) for record in records)


def _integer(row: dict[str, object], key: str) -> int:
    return int(cast(int | float | str, row[key]))


def _number(row: dict[str, object], key: str) -> float | None:
    value = row.get(key)
    if value is None:
        return None
    return float(cast(int | float | str, value))


def _text(row: dict[str, object], key: str) -> str | None:
    value = row.get(key)
    return str(value) if value is not None else None
