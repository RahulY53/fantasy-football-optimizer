"""Framework-independent Monte Carlo simulation records."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SimulationWeekInput:
    """One player's probability and component inputs for one Gameweek."""

    gameweek_id: int
    gameweek: str
    expected_minutes: float
    p_appearance: float
    p_60_plus: float
    appearance_xpts: float
    goal_xpts: float
    assist_xpts: float
    clean_sheet_xpts: float
    save_xpts: float
    bonus_xpts: float
    deduction_xpts: float
    defensive_contribution_xpts: float = 0.0

    @property
    def total_xpts(self) -> float:
        """Return the expected component sum."""

        return (
            self.appearance_xpts
            + self.goal_xpts
            + self.assist_xpts
            + self.clean_sheet_xpts
            + self.save_xpts
            + self.bonus_xpts
            + self.deduction_xpts
            + self.defensive_contribution_xpts
        )


@dataclass(frozen=True, slots=True)
class SimulationPlayerInput:
    """One current player and aligned future probability inputs."""

    player_id: int
    player: str
    position: str
    team: str
    weeks: tuple[SimulationWeekInput, ...]


@dataclass(frozen=True, slots=True)
class HistogramBin:
    """One compact total-points histogram bucket."""

    lower: float
    upper: float
    count: int


@dataclass(frozen=True, slots=True)
class WeekSimulationSummary:
    """Distribution and deterministic decisions for one simulated Gameweek."""

    gameweek_id: int
    gameweek: str
    formation: str
    captain_id: int
    captain: str
    starter_ids: tuple[int, ...]
    expected_points: float
    mean: float
    median: float
    p10: float
    p90: float
    probability_40_plus: float


@dataclass(frozen=True, slots=True)
class PlayerSimulationSummary:
    """One selected player's horizon outcome distribution."""

    player_id: int
    player: str
    position: str
    team: str
    selected_gameweeks: int
    captained_gameweeks: int
    mean: float
    median: float
    p10: float
    p90: float
    blank_probability: float
    return_probability: float
    haul_probability: float


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """Complete reproducible current-team simulation result."""

    iterations: int
    seed: int
    horizon: int
    mean: float
    median: float
    standard_deviation: float
    p10: float
    p25: float
    p75: float
    p90: float
    probability_below_40_per_gw: float
    probability_50_per_gw_plus: float
    probability_60_per_gw_plus: float
    weeks: tuple[WeekSimulationSummary, ...]
    players: tuple[PlayerSimulationSummary, ...]
    histogram: tuple[HistogramBin, ...]
