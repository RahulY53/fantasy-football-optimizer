"""Small composition root shared by UI and API adapters."""

from __future__ import annotations

from dataclasses import dataclass

from fpl_optimizer.config import PROJECT_ROOT, Settings, get_settings
from fpl_optimizer.data.cache import JsonCache
from fpl_optimizer.data.fpl.client import FplClient
from fpl_optimizer.data.fpl.team_service import PublicFplTeamService
from fpl_optimizer.database.base import Database
from fpl_optimizer.odds.providers.odds_api_io import OddsApiIoProvider
from fpl_optimizer.services.analytics import PlayerAnalyticsService
from fpl_optimizer.services.backtesting import BacktestService
from fpl_optimizer.services.changes import ChangeDetectionService
from fpl_optimizer.services.chips import ChipService
from fpl_optimizer.services.forecast import ForecastService
from fpl_optimizer.services.markets import MarketService, OddsImportService
from fpl_optimizer.services.model_lab import ModelLabService
from fpl_optimizer.services.optimizer import SquadOptimizerService
from fpl_optimizer.services.planner import MultiGameweekPlannerService
from fpl_optimizer.services.refresh import RefreshService
from fpl_optimizer.services.simulation import SimulationService
from fpl_optimizer.services.strategy import StrategyService
from fpl_optimizer.services.team import CurrentTeamService
from fpl_optimizer.services.team_import import TeamImportService
from fpl_optimizer.services.transfers import TransferOptimizerService
from fpl_optimizer.services.update_odds import LiveOddsUpdateService
from fpl_optimizer.services.update_team import TeamUpdateService
from fpl_optimizer.services.watchlist import WatchlistService
from fpl_optimizer.services.weekly import WeeklyDecisionService


@dataclass(slots=True)
class AppContainer:
    """Construct and own Phase 1 application dependencies."""

    settings: Settings
    database: Database
    client: FplClient
    refresh: RefreshService
    forecast: ForecastService
    odds_import: OddsImportService
    markets: MarketService
    strategy: StrategyService
    optimizer: SquadOptimizerService
    team: CurrentTeamService
    team_import: TeamImportService
    live_odds: LiveOddsUpdateService
    transfers: TransferOptimizerService
    planner: MultiGameweekPlannerService
    simulation: SimulationService
    chips: ChipService
    backtesting: BacktestService
    update_team: TeamUpdateService
    analytics: PlayerAnalyticsService
    watchlist: WatchlistService
    changes: ChangeDetectionService
    weekly: WeeklyDecisionService
    model_lab: ModelLabService

    @classmethod
    def create(cls, settings: Settings | None = None) -> AppContainer:
        """Build the default local application dependency graph."""

        resolved = settings or get_settings()
        database = Database(resolved.database_url)
        database.create_schema()
        client = FplClient(
            base_url=resolved.fpl_base_url,
            cache=JsonCache(resolved.cache_dir),
            cache_ttl_seconds=resolved.cache_ttl_seconds,
            timeout_seconds=resolved.http_timeout_seconds,
        )
        strategy = StrategyService(database)
        optimizer = SquadOptimizerService(database, strategy)
        live_provider = OddsApiIoProvider(
            resolved.odds_api_key,
            JsonCache(resolved.cache_dir / "odds"),
            base_url=resolved.odds_api_base_url,
            bookmakers=resolved.odds_bookmakers,
            cache_ttl_seconds=resolved.odds_cache_ttl_seconds,
        )
        refresh_service = RefreshService(database, client)
        forecast_service = ForecastService(database)
        team_service = CurrentTeamService(database, strategy, optimizer)
        team_import_service = TeamImportService(database, PublicFplTeamService(client))
        live_odds_service = LiveOddsUpdateService(
            database,
            live_provider,
            PROJECT_ROOT / "config" / "team_aliases.yaml",
            configured=bool(resolved.odds_api_key),
            stale_after_seconds=resolved.odds_stale_after_seconds,
        )
        transfers_service = TransferOptimizerService(database, strategy)
        planner_service = MultiGameweekPlannerService(database, strategy)
        simulation_service = SimulationService(database)
        chips_service = ChipService(database, strategy)
        update_team_service = TeamUpdateService(
            refresh_service,
            team_import_service,
            forecast_service,
            live_odds_service,
            team_service,
            transfers_service,
        )
        weekly_service = WeeklyDecisionService(
            update_team_service,
            team_service,
            transfers_service,
            planner_service,
            simulation_service,
            chips_service,
        )
        model_lab_service = ModelLabService(database, strategy, resolved)
        return cls(
            resolved,
            database,
            client,
            refresh_service,
            forecast_service,
            OddsImportService(database),
            MarketService(database),
            strategy,
            optimizer,
            team_service,
            team_import_service,
            live_odds_service,
            transfers_service,
            planner_service,
            simulation_service,
            chips_service,
            BacktestService(database),
            update_team_service,
            PlayerAnalyticsService(database, strategy),
            WatchlistService(database),
            ChangeDetectionService(database),
            weekly_service,
            model_lab_service,
        )

    def close(self) -> None:
        """Release external resources."""

        self.client.close()
        provider = self.live_odds.provider
        close = getattr(provider, "close", None)
        if callable(close):
            close()
        self.database.engine.dispose()
