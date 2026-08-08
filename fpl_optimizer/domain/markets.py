"""Framework-independent betting market records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fpl_optimizer.domain.enums import OddsMarket, OddsSelection, OddsSnapshotKind
from fpl_optimizer.domain.forecasts import StatisticalComponents


@dataclass(frozen=True, slots=True)
class OddsQuote:
    """One timestamped decimal-odds observation."""

    fixture_fpl_id: int
    provider: str
    bookmaker: str
    market: OddsMarket
    selection: OddsSelection
    decimal_odds: float
    observed_at: datetime
    snapshot_kind: OddsSnapshotKind = OddsSnapshotKind.CURRENT
    source_ref: str = ""


@dataclass(frozen=True, slots=True)
class GoalscorerOddsQuote:
    """One timestamped anytime-goalscorer price linked by official FPL player ID."""

    fixture_fpl_id: int
    player_fpl_id: int
    provider: str
    bookmaker: str
    decimal_odds: float
    observed_at: datetime
    snapshot_kind: OddsSnapshotKind = OddsSnapshotKind.CURRENT
    source_ref: str = ""


@dataclass(frozen=True, slots=True)
class FairMarket:
    """One bookmaker market after margin removal."""

    probabilities: dict[OddsSelection, float]
    overround: float
    method: str
    diagnostic: float | None = None


@dataclass(frozen=True, slots=True)
class ConsensusMarket:
    """Consensus fair probabilities across complete bookmakers."""

    market: OddsMarket
    probabilities: dict[OddsSelection, float]
    dispersion: float
    bookmaker_count: int
    observed_at: datetime
    devig_method: str


@dataclass(frozen=True, slots=True)
class ImpliedGoals:
    """Poisson team goal means fitted to market probabilities."""

    home_xg: float
    away_xg: float
    home_win: float
    draw: float
    away_win: float
    over_2_5: float
    btts_yes: float
    home_over_1_5: float
    away_over_1_5: float
    residual: float
    success: bool


@dataclass(frozen=True, slots=True)
class MarketFixtureOutput:
    """One persisted market-derived fixture forecast."""

    fixture_id: int
    prediction_at: datetime
    input_cutoff_at: datetime
    home_win: float
    draw: float
    away_win: float
    over_2_5: float
    btts_yes: float
    home_over_1_5: float
    away_over_1_5: float
    home_xg: float
    away_xg: float
    home_clean_sheet: float
    away_clean_sheet: float
    dispersion: float
    bookmaker_count: int
    fit_residual: float
    fit_success: bool
    devig_method: str
    advanced_market_count: int


@dataclass(frozen=True, slots=True)
class PlayerMarketOutput:
    """One market-derived player/Gameweek forecast."""

    player_id: int
    gameweek_id: int
    prediction_at: datetime
    input_cutoff_at: datetime
    components: StatisticalComponents
    fixture_count: int
    confidence: str
    explanation: dict[str, object]
    goalscorer_probability: float | None = None
