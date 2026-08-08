"""Application service for initial-squad optimization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fpl_optimizer.database.base import Database
from fpl_optimizer.database.optimization_repository import OptimizationRepository
from fpl_optimizer.domain.optimizer import (
    SquadCandidate,
    SquadOptimizationRequest,
    SquadOptimizationResult,
)
from fpl_optimizer.domain.strategy import StrategyProfile
from fpl_optimizer.optimizer.squad import optimize_squad, validate_result
from fpl_optimizer.services.strategy import StrategyService


@dataclass(frozen=True, slots=True)
class SquadRunReport:
    """Persisted result and run identity returned to adapters."""

    run_id: int
    created_at: datetime
    result: SquadOptimizationResult


class SquadOptimizerService:
    """Connect dynamic strategy scores to the isolated integer program."""

    def __init__(self, database: Database, strategy_service: StrategyService) -> None:
        self.database = database
        self.strategy_service = strategy_service

    def run(
        self,
        profile: StrategyProfile,
        market_weight: float,
        request: SquadOptimizationRequest,
    ) -> SquadRunReport:
        """Generate, validate, and persist the best legal initial squad."""

        scores = self.strategy_service.score(profile, market_weight)
        if not scores:
            raise RuntimeError("Generate statistical forecasts before optimizing a squad")
        candidates = [
            SquadCandidate(
                player_id=score.player_id,
                player=score.player,
                position=score.position,
                team=score.team,
                price=score.price,
                ownership=score.ownership,
                horizon_xpts=score.horizon_xpts,
                risk=score.risk,
                optimization_score=score.score,
            )
            for score in scores
        ]
        result = optimize_squad(candidates, request)
        validate_result(result)
        created_at = datetime.now(UTC)
        with self.database.session() as session:
            row = OptimizationRepository(session).save(
                result=result,
                request=request,
                strategy=profile,
                market_weight=market_weight,
                created_at=created_at,
            )
            run_id = row.id
        return SquadRunReport(run_id=run_id, created_at=created_at, result=result)

    def recent(self) -> list[dict[str, object]]:
        """Return recent initial-squad optimization summaries."""

        with self.database.session() as session:
            return OptimizationRepository(session).recent()

    def latest_squad_player_ids(self) -> tuple[int, ...]:
        """Return player IDs from the latest persisted initial-squad result."""

        with self.database.session() as session:
            return OptimizationRepository(session).latest_squad_player_ids()
