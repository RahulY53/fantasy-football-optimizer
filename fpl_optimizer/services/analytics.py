"""Application service for the reusable player analytics dataset."""

from __future__ import annotations

from fpl_optimizer.analytics.player_dataset import PlayerAnalyticsRecord, build_player_dataset
from fpl_optimizer.database.base import Database
from fpl_optimizer.database.forecast_repository import ForecastRepository
from fpl_optimizer.database.repositories import FplRepository
from fpl_optimizer.domain.strategy import StrategyProfile
from fpl_optimizer.services.strategy import StrategyService


class PlayerAnalyticsService:
    """Join already-calculated player, forecast, and strategy read models."""

    def __init__(self, database: Database, strategy: StrategyService) -> None:
        self.database = database
        self.strategy = strategy

    def dataset(
        self, profile: StrategyProfile, market_weight: float
    ) -> tuple[PlayerAnalyticsRecord, ...]:
        """Return one immutable dataset without rerunning forecasts or optimization."""

        with self.database.session() as session:
            players = FplRepository(session).list_players()
            forecasts = ForecastRepository(session).list_player_summaries(market_weight)
        scores: list[dict[str, object]] = []
        if forecasts:
            scores = [
                {
                    "Player ID": score.player_id,
                    "Optimization Score": score.score,
                    "Value": score.value,
                    "Risk": score.risk,
                }
                for score in self.strategy.score(profile, market_weight)
            ]
        return build_player_dataset(players, forecasts, scores)
