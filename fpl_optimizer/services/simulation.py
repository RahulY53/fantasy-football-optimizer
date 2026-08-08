"""Application service for current-team Monte Carlo simulation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fpl_optimizer.database.base import Database
from fpl_optimizer.database.forecast_repository import ForecastRepository
from fpl_optimizer.database.simulation_repository import SimulationRepository
from fpl_optimizer.database.team_repository import CurrentTeamRepository
from fpl_optimizer.domain.simulation import SimulationPlayerInput, SimulationResult
from fpl_optimizer.simulation.monte_carlo import simulate_current_team


@dataclass(frozen=True, slots=True)
class SimulationRunReport:
    """Persisted simulation and run identity."""

    run_id: int
    created_at: datetime
    result: SimulationResult


class SimulationService:
    """Load aligned forecasts, simulate the current team, and persist the result."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def run(
        self,
        *,
        horizon: int,
        iterations: int,
        seed: int,
        market_weight: float,
    ) -> SimulationRunReport:
        """Run a reproducible fixed-squad Monte Carlo simulation."""

        with self.database.session() as session:
            team = CurrentTeamRepository(session).get()
            if team is None:
                raise RuntimeError("Save a current squad before running a simulation")
            forecast_at, weekly = ForecastRepository(session).simulation_inputs(
                {player.player_id for player in team.players}, horizon, market_weight
            )
        if forecast_at is None:
            raise RuntimeError("Generate advanced forecasts before running a simulation")
        if any(player.player_id not in weekly for player in team.players):
            raise RuntimeError(
                f"Generate forecasts covering at least {horizon} Gameweeks before simulating"
            )
        players = [
            SimulationPlayerInput(
                player_id=player.player_id,
                player=player.player,
                position=player.position,
                team=player.team,
                weeks=weekly[player.player_id],
            )
            for player in team.players
        ]
        result = simulate_current_team(players, iterations=iterations, seed=seed)
        created_at = datetime.now(UTC)
        with self.database.session() as session:
            row = SimulationRepository(session).save(
                team_id=team.team_id,
                result=result,
                market_weight=market_weight,
                forecast_at=forecast_at,
                created_at=created_at,
            )
            run_id = row.id
        return SimulationRunReport(run_id=run_id, created_at=created_at, result=result)

    def recent(self) -> list[dict[str, object]]:
        """Return recent saved simulation runs."""

        with self.database.session() as session:
            return SimulationRepository(session).recent()
