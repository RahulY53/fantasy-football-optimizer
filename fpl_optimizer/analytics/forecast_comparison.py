"""Framework-independent future fixture and forecast comparison read models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast

from fpl_optimizer.analytics.player_dataset import PlayerAnalyticsRecord

FORECAST_HORIZONS = (1, 3, 5, 6)


@dataclass(frozen=True, slots=True)
class ForecastPoint:
    """One selected player's forecast for one future Gameweek."""

    gameweek_id: int
    gameweek_number: int
    gameweek: str
    opponent: str
    fixture_count: int
    attacking_difficulty: float | None
    defensive_difficulty: float | None
    expected_minutes: float
    stat_xpts: float
    market_xpts: float | None
    blended_xpts: float
    cumulative_xpts: float
    confidence: str
    forecasted_at: datetime | None


@dataclass(frozen=True, slots=True)
class ForecastSeries:
    """One player's ordered forecast curve and fixture context."""

    player_id: int
    full_name: str
    team: str
    position: str
    points: tuple[ForecastPoint, ...]


@dataclass(frozen=True, slots=True)
class ForecastComparison:
    """Aligned selected-player forecasts ready for tables, charts, and export."""

    series: tuple[ForecastSeries, ...]
    gameweeks: tuple[str, ...]
    horizon: int
    forecasted_at: datetime | None


def build_forecast_comparison(
    selected: tuple[PlayerAnalyticsRecord, ...],
    details_by_player: dict[int, list[dict[str, object]]],
    horizon: int,
) -> ForecastComparison:
    """Build aligned weekly and cumulative curves from already-persisted forecasts."""

    if horizon not in FORECAST_HORIZONS:
        raise ValueError(f"Forecast horizon must be one of {FORECAST_HORIZONS}")

    series: list[ForecastSeries] = []
    all_gameweeks: dict[int, str] = {}
    timestamps: list[datetime] = []
    for record in selected:
        rows = sorted(
            details_by_player.get(record.player_id, []),
            key=lambda row: _integer(row, "Gameweek number"),
        )[:horizon]
        cumulative = 0.0
        points: list[ForecastPoint] = []
        for row in rows:
            blended_xpts = _number(row, "Blended xPts") or 0.0
            cumulative += blended_xpts
            forecasted_at = _datetime(row, "Forecasted")
            if forecasted_at is not None:
                timestamps.append(forecasted_at)
            gameweek_number = _integer(row, "Gameweek number")
            gameweek = str(row["Gameweek"])
            all_gameweeks[gameweek_number] = gameweek
            points.append(
                ForecastPoint(
                    gameweek_id=_integer(row, "Gameweek ID"),
                    gameweek_number=gameweek_number,
                    gameweek=gameweek,
                    opponent=str(row.get("Opponent") or "Blank"),
                    fixture_count=_integer(row, "Fixtures"),
                    attacking_difficulty=_number(row, "Attacking difficulty"),
                    defensive_difficulty=_number(row, "Defensive difficulty"),
                    expected_minutes=_number(row, "Expected minutes") or 0.0,
                    stat_xpts=_number(row, "Stat xPts") or 0.0,
                    market_xpts=_number(row, "Market xPts"),
                    blended_xpts=blended_xpts,
                    cumulative_xpts=cumulative,
                    confidence=str(row.get("Confidence") or "Unknown"),
                    forecasted_at=forecasted_at,
                )
            )
        if points:
            series.append(
                ForecastSeries(
                    player_id=record.player_id,
                    full_name=record.full_name,
                    team=record.team,
                    position=record.position,
                    points=tuple(points),
                )
            )

    ordered_gameweeks = tuple(all_gameweeks[key] for key in sorted(all_gameweeks)[:horizon])
    return ForecastComparison(
        series=tuple(series),
        gameweeks=ordered_gameweeks,
        horizon=horizon,
        forecasted_at=max(timestamps) if timestamps else None,
    )


def fixture_comparison_rows(comparison: ForecastComparison) -> list[dict[str, object]]:
    """Return a compact, wide fixture table for the selected players."""

    rows: list[dict[str, object]] = []
    for player in comparison.series:
        row: dict[str, object] = {
            "Full Name": player.full_name,
            "Team": player.team,
            "Position": player.position,
        }
        by_gameweek = {point.gameweek: point for point in player.points}
        for gameweek in comparison.gameweeks:
            point = by_gameweek.get(gameweek)
            row[gameweek] = _fixture_label(point) if point else "—"
        rows.append(row)
    return rows


def forecast_export_rows(comparison: ForecastComparison) -> list[dict[str, object]]:
    """Return raw long-form forecast rows suitable for a CSV export."""

    rows: list[dict[str, object]] = []
    for player in comparison.series:
        for point in player.points:
            rows.append(
                {
                    "Player ID": player.player_id,
                    "Full Name": player.full_name,
                    "Team": player.team,
                    "Position": player.position,
                    "Gameweek": point.gameweek,
                    "Opponent": point.opponent,
                    "Fixture Count": point.fixture_count,
                    "Attacking Difficulty": point.attacking_difficulty,
                    "Defensive Difficulty": point.defensive_difficulty,
                    "Expected Minutes": point.expected_minutes,
                    "Stat xPts": point.stat_xpts,
                    "Market xPts": point.market_xpts,
                    "Blended xPts": point.blended_xpts,
                    "Cumulative xPts": point.cumulative_xpts,
                    "Confidence": point.confidence,
                    "Forecasted": point.forecasted_at,
                }
            )
    return rows


def _fixture_label(point: ForecastPoint) -> str:
    if point.fixture_count == 0:
        return "Blank"
    attack = (
        f"A {point.attacking_difficulty:.1f}"
        if point.attacking_difficulty is not None
        else "A —"
    )
    defence = (
        f"D {point.defensive_difficulty:.1f}"
        if point.defensive_difficulty is not None
        else "D —"
    )
    return f"{point.opponent} · {attack} · {defence}"


def _integer(row: dict[str, object], key: str) -> int:
    return int(cast(int | float | str, row[key]))


def _number(row: dict[str, object], key: str) -> float | None:
    value = row.get(key)
    return float(cast(int | float | str, value)) if value is not None else None


def _datetime(row: dict[str, object], key: str) -> datetime | None:
    return cast(datetime | None, row.get(key))
