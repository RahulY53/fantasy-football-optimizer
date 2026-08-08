"""Application service for independent user-preference scoring."""

from __future__ import annotations

from fpl_optimizer.database.base import Database
from fpl_optimizer.database.strategy_repository import StrategyRepository
from fpl_optimizer.domain.strategy import PlayerStrategyScore, StrategyProfile
from fpl_optimizer.scoring.optimization_score import score_players


class StrategyService:
    """Score forecasted players and persist named user profiles."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def score(self, profile: StrategyProfile, market_weight: float) -> list[PlayerStrategyScore]:
        """Calculate dynamic strategy scores without modifying any forecast."""

        with self.database.session() as session:
            inputs = StrategyRepository(session).player_inputs(market_weight, profile.horizon)
        return score_players(inputs, profile)

    def save(self, profile: StrategyProfile) -> int:
        """Save a named local strategy and return its database ID."""

        if not profile.name.strip():
            raise ValueError("Strategy name cannot be blank")
        with self.database.session() as session:
            row = StrategyRepository(session).save(profile)
            session.flush()
            return row.id

    def list_saved(self) -> list[dict[str, object]]:
        """Return saved local strategy profiles."""

        with self.database.session() as session:
            return StrategyRepository(session).list_saved()
