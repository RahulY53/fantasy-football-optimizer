"""Strict-enough mapping from provider JSON into canonical records."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fpl_optimizer.domain.enums import FixtureStatus, Position
from fpl_optimizer.domain.records import (
    BootstrapData,
    FixtureRecord,
    GameweekRecord,
    PlayerRecord,
    TeamRecord,
)


class FplMappingError(ValueError):
    """Raised when a provider payload lacks required structural fields."""


POSITION_BY_TYPE = {
    1: Position.GOALKEEPER,
    2: Position.DEFENDER,
    3: Position.MIDFIELDER,
    4: Position.FORWARD,
}


def map_bootstrap(payload: Any) -> BootstrapData:
    """Map `/bootstrap-static/` JSON into canonical records."""

    if not isinstance(payload, dict):
        raise FplMappingError("Bootstrap payload must be an object")
    teams_raw = _list(payload, "teams")
    events_raw = _list(payload, "events")
    players_raw = _list(payload, "elements")

    teams = tuple(
        TeamRecord(
            fpl_id=_int(item, "id"),
            name=_str(item, "name"),
            short_name=_str(item, "short_name"),
            strength=_int(item, "strength", 0),
            strength_attack_home=_int(item, "strength_attack_home", 0),
            strength_attack_away=_int(item, "strength_attack_away", 0),
            strength_defence_home=_int(item, "strength_defence_home", 0),
            strength_defence_away=_int(item, "strength_defence_away", 0),
        )
        for item in teams_raw
    )
    gameweeks = tuple(
        GameweekRecord(
            fpl_id=_int(item, "id"),
            name=_str(item, "name"),
            deadline_at=_datetime(item.get("deadline_time"), "deadline_time"),
            is_current=bool(item.get("is_current", False)),
            is_next=bool(item.get("is_next", False)),
            finished=bool(item.get("finished", False)),
        )
        for item in events_raw
    )
    players: list[PlayerRecord] = []
    for item in players_raw:
        element_type = _int(item, "element_type")
        try:
            position = POSITION_BY_TYPE[element_type]
        except KeyError as error:
            raise FplMappingError(f"Unknown element_type: {element_type}") from error
        players.append(
            PlayerRecord(
                fpl_id=_int(item, "id"),
                team_fpl_id=_int(item, "team"),
                position=position,
                web_name=_str(item, "web_name"),
                first_name=_str(item, "first_name", ""),
                second_name=_str(item, "second_name", ""),
                status=_str(item, "status", "u"),
                news=_str(item, "news", ""),
                chance_next_round=_optional_int(item.get("chance_of_playing_next_round")),
                price_tenths=_int(item, "now_cost"),
                total_points=_int(item, "total_points", 0),
                minutes=_int(item, "minutes", 0),
                starts=_int(item, "starts", 0),
                goals=_int(item, "goals_scored", 0),
                assists=_int(item, "assists", 0),
                clean_sheets=_int(item, "clean_sheets", 0),
                saves=_int(item, "saves", 0),
                bonus=_int(item, "bonus", 0),
                bps=_int(item, "bps", 0),
                selected_pct=_float(item, "selected_by_percent", 0.0),
                transfers_in=_int(item, "transfers_in", 0),
                transfers_out=_int(item, "transfers_out", 0),
                form=_float(item, "form", 0.0),
                points_per_game=_float(item, "points_per_game", 0.0),
                ict_index=_float(item, "ict_index", 0.0),
                own_goals=_int(item, "own_goals", 0),
                penalties_saved=_int(item, "penalties_saved", 0),
                penalties_missed=_int(item, "penalties_missed", 0),
                yellow_cards=_int(item, "yellow_cards", 0),
                red_cards=_int(item, "red_cards", 0),
                clearances_blocks_interceptions=_int(
                    item, "clearances_blocks_interceptions", 0
                ),
                tackles=_int(item, "tackles", 0),
                recoveries=_int(item, "recoveries", 0),
                defensive_contribution=_int(item, "defensive_contribution", 0),
            )
        )
    if not teams or not gameweeks:
        raise FplMappingError("Bootstrap payload contains no teams or gameweeks")
    return BootstrapData(teams=teams, gameweeks=gameweeks, players=tuple(players))


def map_fixtures(payload: Any) -> tuple[FixtureRecord, ...]:
    """Map `/fixtures/` JSON into canonical records."""

    if not isinstance(payload, list):
        raise FplMappingError("Fixtures payload must be a list")
    records: list[FixtureRecord] = []
    for item in payload:
        if not isinstance(item, dict):
            raise FplMappingError("Each fixture must be an object")
        started = bool(item.get("started", False))
        finished = bool(item.get("finished", False))
        status = (
            FixtureStatus.FINISHED
            if finished
            else FixtureStatus.STARTED
            if started
            else FixtureStatus.SCHEDULED
        )
        records.append(
            FixtureRecord(
                fpl_id=_int(item, "id"),
                gameweek_fpl_id=_optional_int(item.get("event")),
                home_team_fpl_id=_int(item, "team_h"),
                away_team_fpl_id=_int(item, "team_a"),
                kickoff_at=(
                    _datetime(item["kickoff_time"], "kickoff_time")
                    if item.get("kickoff_time")
                    else None
                ),
                home_difficulty=_int(item, "team_h_difficulty", 0),
                away_difficulty=_int(item, "team_a_difficulty", 0),
                status=status,
                home_score=_optional_int(item.get("team_h_score")),
                away_score=_optional_int(item.get("team_a_score")),
            )
        )
    return tuple(records)


def _list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise FplMappingError(f"{key} must be a list of objects")
    return value


def _str(item: dict[str, Any], key: str, default: str | None = None) -> str:
    value = item.get(key, default)
    if value is None:
        if default is not None:
            return default
        raise FplMappingError(f"Missing string field: {key}")
    return str(value)


def _int(item: dict[str, Any], key: str, default: int | None = None) -> int:
    value = item.get(key, default)
    if value is None:
        if default is not None:
            return default
        raise FplMappingError(f"Missing integer field: {key}")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise FplMappingError(f"Invalid integer field: {key}") from error


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise FplMappingError("Invalid optional integer") from error


def _float(item: dict[str, Any], key: str, default: float | None = None) -> float:
    value = item.get(key, default)
    if value in (None, ""):
        if default is None:
            raise FplMappingError(f"Missing float field: {key}")
        return default
    assert value is not None
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise FplMappingError(f"Invalid float field: {key}") from error


def _datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise FplMappingError(f"Missing datetime field: {field}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise FplMappingError(f"Invalid datetime field: {field}") from error
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
