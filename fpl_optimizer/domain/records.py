"""Typed canonical records emitted by ingestion mappers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fpl_optimizer.domain.enums import FixtureStatus, Position


@dataclass(frozen=True, slots=True)
class TeamRecord:
    """A canonical Premier League team snapshot."""

    fpl_id: int
    name: str
    short_name: str
    strength: int
    strength_attack_home: int
    strength_attack_away: int
    strength_defence_home: int
    strength_defence_away: int


@dataclass(frozen=True, slots=True)
class GameweekRecord:
    """An FPL event and its deadline state."""

    fpl_id: int
    name: str
    deadline_at: datetime
    is_current: bool
    is_next: bool
    finished: bool


@dataclass(frozen=True, slots=True)
class PlayerRecord:
    """A canonical player plus the current public snapshot fields."""

    fpl_id: int
    team_fpl_id: int
    position: Position
    web_name: str
    first_name: str
    second_name: str
    status: str
    news: str
    chance_next_round: int | None
    price_tenths: int
    total_points: int
    minutes: int
    starts: int
    goals: int
    assists: int
    clean_sheets: int
    saves: int
    bonus: int
    bps: int
    selected_pct: float
    transfers_in: int
    transfers_out: int
    form: float
    points_per_game: float
    ict_index: float


@dataclass(frozen=True, slots=True)
class FixtureRecord:
    """A canonical Premier League fixture."""

    fpl_id: int
    gameweek_fpl_id: int | None
    home_team_fpl_id: int
    away_team_fpl_id: int
    kickoff_at: datetime | None
    home_difficulty: int
    away_difficulty: int
    status: FixtureStatus
    home_score: int | None
    away_score: int | None


@dataclass(frozen=True, slots=True)
class BootstrapData:
    """Mapped contents of the FPL bootstrap response."""

    teams: tuple[TeamRecord, ...]
    gameweeks: tuple[GameweekRecord, ...]
    players: tuple[PlayerRecord, ...]
