"""Framework-independent records for the basic statistical forecast."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fpl_optimizer.domain.enums import Position


@dataclass(frozen=True, slots=True)
class PlayerForecastInput:
    """Latest player data required by the Phase 2 forecast model."""

    player_id: int
    fpl_id: int
    team_id: int
    position: Position
    web_name: str
    status: str
    chance_next_round: int | None
    minutes: int
    starts: int
    goals: int
    assists: int
    saves: int
    bonus: int
    price_tenths: int
    total_points: int = 0
    clean_sheets: int = 0
    bps: int = 0
    selected_pct: float = 0.0
    transfers_in: int = 0
    transfers_out: int = 0
    form: float = 0.0
    points_per_game: float = 0.0
    ict_index: float = 0.0


@dataclass(frozen=True, slots=True)
class TeamStrength:
    """Home/away attacking and defensive inputs for one team."""

    team_id: int
    name: str
    short_name: str
    attack_home: int
    attack_away: int
    defence_home: int
    defence_away: int


@dataclass(frozen=True, slots=True)
class ForecastFixture:
    """A future fixture used to project both participating teams."""

    fixture_id: int
    gameweek_id: int
    home_team_id: int
    away_team_id: int
    home_difficulty: int
    away_difficulty: int


@dataclass(frozen=True, slots=True)
class ExpectedMinutes:
    """Explainable appearance scenarios for one player in one fixture."""

    expected_minutes: float
    p_start: float
    p_sub_appearance: float
    p_appearance: float
    p_60_plus: float
    minutes_if_start: float
    minutes_if_sub: float
    availability: float
    confidence: str


@dataclass(frozen=True, slots=True)
class StatisticalComponents:
    """Expected FPL point components for one fixture."""

    appearance: float
    goals: float
    assists: float
    clean_sheet: float
    saves: float
    bonus: float
    deductions: float

    @property
    def total(self) -> float:
        """Return the component sum without display rounding."""

        return (
            self.appearance
            + self.goals
            + self.assists
            + self.clean_sheet
            + self.saves
            + self.bonus
            + self.deductions
        )


@dataclass(frozen=True, slots=True)
class ForecastOutput:
    """One persisted player/Gameweek forecast."""

    player_id: int
    gameweek_id: int
    prediction_at: datetime
    input_cutoff_at: datetime
    expected_minutes: float
    components: StatisticalComponents
    fixture_count: int
    opponent_summary: str
    confidence: str
    explanation: dict[str, object]
