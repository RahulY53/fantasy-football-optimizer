"""Application service for four-chip opportunity evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fpl_optimizer.database.base import Database
from fpl_optimizer.database.chip_repository import ChipRepository
from fpl_optimizer.database.forecast_repository import ForecastRepository
from fpl_optimizer.database.team_repository import CurrentTeamRepository
from fpl_optimizer.domain.chips import ChipCandidate, ChipEvaluation
from fpl_optimizer.domain.strategy import StrategyProfile
from fpl_optimizer.optimizer.chips import evaluate_chips
from fpl_optimizer.services.strategy import StrategyService


@dataclass(frozen=True, slots=True)
class ChipRunReport:
    """Persisted chip evaluation and run identity."""

    run_id: int
    created_at: datetime
    evaluation: ChipEvaluation


class ChipService:
    """Assemble current data, evaluate chips, and persist the result."""

    def __init__(self, database: Database, strategy_service: StrategyService) -> None:
        self.database = database
        self.strategy_service = strategy_service

    def run(
        self,
        profile: StrategyProfile,
        market_weight: float,
        horizon: int,
    ) -> ChipRunReport:
        """Evaluate all four chips over the selected horizon."""

        with self.database.session() as session:
            team = CurrentTeamRepository(session).get()
            forecast_repository = ForecastRepository(session)
            forecast_at = forecast_repository.latest_prediction_at()
            gameweeks, matrix = forecast_repository.planning_matrix(horizon, market_weight)
        if team is None:
            raise RuntimeError("Save a current squad before evaluating chips")
        if forecast_at is None or not gameweeks:
            raise RuntimeError(
                f"Generate forecasts covering at least {horizon} Gameweeks before evaluating chips"
            )
        scores = self.strategy_service.score(profile, market_weight)
        current_ids = {player.player_id for player in team.players}
        selling_prices = {player.player_id: player.selling_price for player in team.players}
        if any(player_id not in matrix for player_id in current_ids):
            raise RuntimeError("One or more current players are missing chip forecasts")
        candidates = [
            ChipCandidate(
                player_id=score.player_id,
                player=score.player,
                position=score.position,
                team=score.team,
                price=selling_prices.get(score.player_id, score.price),
                optimization_score=score.score,
                gameweek_xpts=matrix[score.player_id],
            )
            for score in scores
            if score.player_id in matrix
        ]
        budget = team.bank + sum(player.selling_price for player in team.players)
        evaluation = evaluate_chips(
            candidates,
            current_ids=current_ids,
            budget=budget,
            gameweeks=gameweeks,
            availability={
                "Wildcard": team.wildcard_available,
                "Free Hit": team.free_hit_available,
                "Bench Boost": team.bench_boost_available,
                "Triple Captain": team.triple_captain_available,
            },
        )
        created_at = datetime.now(UTC)
        with self.database.session() as session:
            row = ChipRepository(session).save(
                team_id=team.team_id,
                evaluation=evaluation,
                strategy=profile,
                market_weight=market_weight,
                forecast_at=forecast_at,
                created_at=created_at,
            )
            run_id = row.id
        return ChipRunReport(run_id=run_id, created_at=created_at, evaluation=evaluation)

    def recent(self) -> list[dict[str, object]]:
        """Return recent saved chip evaluations."""

        with self.database.session() as session:
            return ChipRepository(session).recent()
