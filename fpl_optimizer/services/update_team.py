"""One-action public team, forecasts, live odds, lineup, and transfer update."""

from __future__ import annotations

from dataclasses import dataclass

from fpl_optimizer.domain.strategy import StrategyProfile
from fpl_optimizer.domain.team import PublishedTeamSummary
from fpl_optimizer.services.forecast import ForecastReport, ForecastService
from fpl_optimizer.services.refresh import RefreshReport, RefreshService
from fpl_optimizer.services.team import CurrentTeamService, LineupRunReport
from fpl_optimizer.services.team_import import TeamImportService
from fpl_optimizer.services.transfers import TransferOptimizerService, TransferRunReport
from fpl_optimizer.services.update_odds import LiveOddsRefreshReport, LiveOddsUpdateService


@dataclass(frozen=True, slots=True)
class TeamUpdateReport:
    """Outputs and transparent fallbacks from the one-action workflow."""

    refresh: RefreshReport
    imported_team: PublishedTeamSummary
    forecast: ForecastReport
    odds: LiveOddsRefreshReport | None
    lineup: LineupRunReport
    transfers: TransferRunReport
    warnings: tuple[str, ...]


class TeamUpdateService:
    """Orchestrate existing modular services without changing optimizer mathematics."""

    def __init__(
        self,
        refresh: RefreshService,
        team_import: TeamImportService,
        forecast: ForecastService,
        live_odds: LiveOddsUpdateService,
        team: CurrentTeamService,
        transfers: TransferOptimizerService,
    ) -> None:
        self.refresh_service = refresh
        self.team_import = team_import
        self.forecast_service = forecast
        self.live_odds = live_odds
        self.team = team
        self.transfers = transfers

    def run(
        self,
        team_id: int,
        profile: StrategyProfile,
        market_weight: float,
    ) -> TeamUpdateReport:
        """Refresh all inputs, then produce lineup and transfer recommendations."""

        refresh = self.refresh_service.refresh(force=False)
        imported = self.team_import.import_team(team_id, force=True)
        forecast = self.forecast_service.run(horizon=6)
        odds: LiveOddsRefreshReport | None = None
        warnings: list[str] = list(refresh.warnings)
        try:
            odds = self.live_odds.refresh(force=False)
            warnings.extend(odds.warnings)
        except RuntimeError as error:
            warnings.append(
                f"Market forecast unavailable; using statistical forecast only: {error}"
            )
        lineup = self.team.optimize(profile, market_weight)
        transfers = self.transfers.run(profile, market_weight)
        return TeamUpdateReport(
            refresh, imported, forecast, odds, lineup, transfers, tuple(warnings)
        )
