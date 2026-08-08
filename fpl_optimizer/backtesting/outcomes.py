"""Strict CSV parsing for historical player/Gameweek outcomes."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from fpl_optimizer.domain.backtesting import HistoricalOutcomeInput

REQUIRED_COLUMNS = {"player_id", "gameweek", "actual_points"}
OPTIONAL_INTEGER_COLUMNS = (
    "actual_minutes",
    "goals",
    "assists",
    "clean_sheets",
    "saves",
    "bonus",
)


def parse_outcomes_csv(content: str) -> list[HistoricalOutcomeInput]:
    """Validate a complete outcome CSV before returning any rows."""

    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    headings = set(reader.fieldnames or ())
    missing = REQUIRED_COLUMNS - headings
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    outcomes: list[HistoricalOutcomeInput] = []
    seen: set[tuple[int, int]] = set()
    for line_number, row in enumerate(reader, start=2):
        try:
            player_id = _positive_int(row["player_id"], "player_id")
            gameweek = _positive_int(row["gameweek"], "gameweek")
            points = float(row["actual_points"])
            if not -20 <= points <= 100:
                raise ValueError("actual_points must be between -20 and 100")
            values = {
                name: _optional_non_negative_int(row.get(name), name)
                for name in OPTIONAL_INTEGER_COLUMNS
            }
            finalized = _optional_datetime(row.get("finalized_at"))
        except (TypeError, ValueError) as error:
            raise ValueError(f"Row {line_number}: {error}") from error
        key = (player_id, gameweek)
        if key in seen:
            raise ValueError(f"Row {line_number}: duplicate player_id and gameweek")
        seen.add(key)
        outcomes.append(
            HistoricalOutcomeInput(
                player_fpl_id=player_id,
                gameweek_fpl_id=gameweek,
                actual_points=points,
                actual_minutes=values["actual_minutes"],
                goals=values["goals"],
                assists=values["assists"],
                clean_sheets=values["clean_sheets"],
                saves=values["saves"],
                bonus=values["bonus"],
                finalized_at=finalized,
            )
        )
    if not outcomes:
        raise ValueError("The CSV contains no outcome rows")
    return outcomes


def _positive_int(value: str | None, name: str) -> int:
    parsed = int(value or "")
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _optional_non_negative_int(value: str | None, name: str) -> int | None:
    if value is None or not value.strip():
        return None
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"{name} cannot be negative")
    return parsed


def _optional_datetime(value: str | None) -> datetime | None:
    if value is None or not value.strip():
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
