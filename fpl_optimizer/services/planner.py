"""Application service for joint multi-Gameweek planning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fpl_optimizer.database.base import Database
from fpl_optimizer.database.forecast_repository import ForecastRepository
from fpl_optimizer.database.planner_repository import PlannerRepository
from fpl_optimizer.database.team_repository import CurrentTeamRepository
from fpl_optimizer.domain.planner import MultiGameweekPlan, PlanningCandidate
from fpl_optimizer.domain.strategy import StrategyProfile
from fpl_optimizer.optimizer.planner import optimize_multi_gameweek
from fpl_optimizer.services.strategy import StrategyService

ALTERNATIVES_PER_POSITION = 35


@dataclass(frozen=True, slots=True)
class PlannerRunReport:
    """Persisted multi-Gameweek plan and run identity."""

    run_id: int
    created_at: datetime
    plan: MultiGameweekPlan


class MultiGameweekPlannerService:
    """Assemble current data, solve a joint plan, and persist it."""

    def __init__(self, database: Database, strategy_service: StrategyService) -> None:
        self.database = database
        self.strategy_service = strategy_service

    def run(
        self,
        profile: StrategyProfile,
        market_weight: float,
        horizon: int,
    ) -> PlannerRunReport:
        """Generate and save an exact two-to-six-Gameweek plan."""

        with self.database.session() as session:
            team = CurrentTeamRepository(session).get()
            forecast_repository = ForecastRepository(session)
            forecast_at = forecast_repository.latest_prediction_at()
            gameweeks, matrix = forecast_repository.planning_matrix(horizon, market_weight)
        if team is None:
            raise RuntimeError("Save a current squad before generating a multi-Gameweek plan")
        if forecast_at is None or not gameweeks:
            raise RuntimeError(
                f"Generate forecasts covering at least {horizon} Gameweeks before planning"
            )
        scores = self.strategy_service.score(profile, market_weight)
        current = {player.player_id: player for player in team.players}
        if any(player_id not in matrix for player_id in current):
            raise RuntimeError("One or more current players are missing planned-Gameweek forecasts")
        all_candidates = [
            PlanningCandidate(
                player_id=score.player_id,
                player=score.player,
                position=score.position,
                team=score.team,
                buy_price=score.price,
                selling_price=(
                    current[score.player_id].selling_price
                    if score.player_id in current
                    else score.price
                ),
                optimization_score=score.score,
                is_current=score.player_id in current,
                gameweek_xpts=matrix[score.player_id],
            )
            for score in scores
            if score.player_id in matrix
        ]
        candidates = _shortlist(all_candidates)
        plan = optimize_multi_gameweek(
            candidates,
            gameweeks=gameweeks,
            bank=team.bank,
            free_transfers=team.free_transfers,
        )
        created_at = datetime.now(UTC)
        with self.database.session() as session:
            row = PlannerRepository(session).save(
                team_id=team.team_id,
                plan=plan,
                strategy=profile,
                market_weight=market_weight,
                forecast_at=forecast_at,
                created_at=created_at,
            )
            run_id = row.id
        return PlannerRunReport(run_id=run_id, created_at=created_at, plan=plan)

    def recent(self) -> list[dict[str, object]]:
        """Return recent saved multi-Gameweek plans."""

        with self.database.session() as session:
            return PlannerRepository(session).recent()


def _shortlist(candidates: list[PlanningCandidate]) -> list[PlanningCandidate]:
    """Keep every current player plus the strongest horizon alternatives by position."""

    selected = [player for player in candidates if player.is_current]
    for position in ("GK", "DEF", "MID", "FWD"):
        alternatives = sorted(
            (
                player
                for player in candidates
                if not player.is_current and player.position == position
            ),
            key=lambda player: (
                sum(player.gameweek_xpts),
                max(player.gameweek_xpts),
                player.optimization_score,
                -player.player_id,
            ),
            reverse=True,
        )
        selected.extend(alternatives[:ALTERNATIVES_PER_POSITION])
    return sorted(selected, key=lambda player: player.player_id)
