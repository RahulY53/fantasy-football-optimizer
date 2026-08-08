"""Application service for current-team transfer decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fpl_optimizer.database.base import Database
from fpl_optimizer.database.forecast_repository import ForecastRepository
from fpl_optimizer.database.team_repository import CurrentTeamRepository
from fpl_optimizer.database.transfer_repository import TransferRepository
from fpl_optimizer.domain.strategy import StrategyProfile
from fpl_optimizer.domain.transfers import TransferCandidate, TransferEvaluation
from fpl_optimizer.optimizer.transfers import evaluate_transfers
from fpl_optimizer.services.strategy import StrategyService


@dataclass(frozen=True, slots=True)
class TransferRunReport:
    """Persisted transfer evaluation and run identity."""

    run_id: int
    created_at: datetime
    evaluation: TransferEvaluation


class TransferOptimizerService:
    """Evaluate roll, one transfer, and two transfers for the current team."""

    def __init__(self, database: Database, strategy_service: StrategyService) -> None:
        self.database = database
        self.strategy_service = strategy_service

    def run(self, profile: StrategyProfile, market_weight: float) -> TransferRunReport:
        """Generate and persist a complete transfer decision comparison."""

        with self.database.session() as session:
            team = CurrentTeamRepository(session).get()
            forecast_at = ForecastRepository(session).latest_prediction_at()
        if team is None:
            raise RuntimeError("Save a current squad before evaluating transfers")
        if forecast_at is None:
            raise RuntimeError("Generate statistical forecasts before evaluating transfers")
        scores = self.strategy_service.score(profile, market_weight)
        if not scores:
            raise RuntimeError("No current player forecasts are available")
        current = {player.player_id: player for player in team.players}
        if any(player_id not in {score.player_id for score in scores} for player_id in current):
            raise RuntimeError("One or more current players are missing forecasts")
        candidates = [
            TransferCandidate(
                player_id=score.player_id,
                player=score.player,
                position=score.position,
                team=score.team,
                buy_price=score.price,
                selling_price=(
                    current[score.player_id].selling_price
                    if score.player_id in current
                    else None
                ),
                horizon_xpts=score.horizon_xpts,
                optimization_score=score.score,
                is_current=score.player_id in current,
            )
            for score in scores
        ]
        evaluation = evaluate_transfers(
            candidates,
            bank=team.bank,
            free_transfers=team.free_transfers,
            transfer_reluctance=profile.transfer_reluctance,
            horizon=profile.horizon,
        )
        created_at = datetime.now(UTC)
        with self.database.session() as session:
            row = TransferRepository(session).save(
                team_id=team.team_id,
                evaluation=evaluation,
                strategy=profile,
                market_weight=market_weight,
                forecast_at=forecast_at,
                created_at=created_at,
            )
            run_id = row.id
        return TransferRunReport(run_id=run_id, created_at=created_at, evaluation=evaluation)

    def recent(self) -> list[dict[str, object]]:
        """Return recent saved transfer decisions."""

        with self.database.session() as session:
            return TransferRepository(session).recent()
