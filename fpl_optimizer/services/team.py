"""Current-team persistence and lineup orchestration."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select

from fpl_optimizer.database.base import Database
from fpl_optimizer.database.forecast_repository import ForecastRepository
from fpl_optimizer.database.models import Player, Team
from fpl_optimizer.database.repositories import FplRepository
from fpl_optimizer.database.team_repository import CurrentTeamRepository
from fpl_optimizer.domain.strategy import StrategyProfile
from fpl_optimizer.domain.team import (
    CurrentTeam,
    CurrentTeamInput,
    CurrentTeamPlayerInput,
    LineupCandidate,
    LineupResult,
)
from fpl_optimizer.optimizer.lineup import optimize_lineup, validate_lineup
from fpl_optimizer.optimizer.squad import MAX_PER_TEAM, POSITION_LIMITS, SQUAD_SIZE
from fpl_optimizer.services.optimizer import SquadOptimizerService
from fpl_optimizer.services.strategy import StrategyService


@dataclass(frozen=True, slots=True)
class LineupRunReport:
    """Persisted lineup result and run identity."""

    run_id: int
    created_at: datetime
    result: LineupResult


class CurrentTeamService:
    """Manage one local current squad and optimize its next-Gameweek lineup."""

    def __init__(
        self,
        database: Database,
        strategy_service: StrategyService,
        squad_optimizer: SquadOptimizerService,
    ) -> None:
        self.database = database
        self.strategy_service = strategy_service
        self.squad_optimizer = squad_optimizer

    def save(self, value: CurrentTeamInput) -> int:
        """Validate and persist a complete current team."""

        self._validate_input(value)
        with self.database.session() as session:
            row = CurrentTeamRepository(session).save(value)
            session.flush()
            return row.id

    def get(self) -> CurrentTeam | None:
        """Return the current locally saved team."""

        with self.database.session() as session:
            return CurrentTeamRepository(session).get()

    def player_choices(self) -> list[dict[str, object]]:
        """Return current canonical players for the team editor."""

        with self.database.session() as session:
            return FplRepository(session).list_players()

    def latest_optimized_input(self) -> CurrentTeamInput | None:
        """Build an editable current-team input from the last Phase 5 squad."""

        player_ids = self.squad_optimizer.latest_squad_player_ids()
        if not player_ids:
            return None
        rows = {cast(int, row["Player ID"]): row for row in self.player_choices()}
        if any(player_id not in rows for player_id in player_ids):
            return None
        return CurrentTeamInput(
            name="My Team",
            bank=0.0,
            free_transfers=1,
            wildcard_available=True,
            free_hit_available=True,
            bench_boost_available=True,
            triple_captain_available=True,
            players=tuple(
                CurrentTeamPlayerInput(
                    player_id=player_id,
                    purchase_price=cast(float, rows[player_id]["Price"]),
                    selling_price=cast(float, rows[player_id]["Price"]),
                )
                for player_id in player_ids
            ),
        )

    def optimize(self, profile: StrategyProfile, market_weight: float) -> LineupRunReport:
        """Optimize and persist the next-Gameweek lineup for the current squad."""

        team = self.get()
        if team is None:
            raise RuntimeError("Save a current squad before optimizing its lineup")
        scores = {
            score.player_id: score
            for score in self.strategy_service.score(profile, market_weight)
        }
        with self.database.session() as session:
            forecast_repository = ForecastRepository(session)
            forecast_at = forecast_repository.latest_prediction_at()
            summaries = {
                cast(int, row["Player ID"]): row
                for row in forecast_repository.list_player_summaries(market_weight)
            }
            source_players = {
                cast(int, row["Player ID"]): row
                for row in FplRepository(session).list_players()
            }
        if forecast_at is None:
            raise RuntimeError("Generate statistical forecasts before optimizing a lineup")
        candidates: list[LineupCandidate] = []
        for player in team.players:
            summary = summaries.get(player.player_id)
            score = scores.get(player.player_id)
            source = source_players.get(player.player_id)
            if summary is None or score is None or source is None:
                raise RuntimeError(f"Missing current forecast for {player.player}")
            candidates.append(
                LineupCandidate(
                    player_id=player.player_id,
                    player=player.player,
                    position=player.position,
                    team=player.team,
                    opponent=str(summary["Opponent"]),
                    current_price=player.current_price,
                    selling_price=player.selling_price,
                    expected_minutes=cast(float, summary["Expected minutes"]),
                    next_gw_xpts=cast(float, summary["Blended xPts"]),
                    next_3_xpts=cast(float, summary["3GW xPts"]),
                    next_5_xpts=cast(float, summary["5GW xPts"]),
                    attacking_xpts=cast(float, summary["Attacking xPts"]),
                    ownership=cast(float, source["Ownership %"]),
                    risk=score.risk,
                )
            )
        result = optimize_lineup(candidates)
        validate_lineup(result)
        created_at = datetime.now(UTC)
        with self.database.session() as session:
            row = CurrentTeamRepository(session).save_lineup(
                team_id=team.team_id,
                result=result,
                profile=profile,
                market_weight=market_weight,
                forecast_at=forecast_at,
                created_at=created_at,
            )
            run_id = row.id
        return LineupRunReport(run_id=run_id, created_at=created_at, result=result)

    def recent_lineups(self) -> list[dict[str, object]]:
        """Return recent saved lineup recommendations."""

        with self.database.session() as session:
            return CurrentTeamRepository(session).recent_lineups()

    def _validate_input(self, value: CurrentTeamInput) -> None:
        if value.name != "My Team":
            raise ValueError("The local current team must be named My Team")
        if value.bank < 0:
            raise ValueError("Bank cannot be negative")
        if not 0 <= value.free_transfers <= 5:
            raise ValueError("Free transfers must be between zero and five")
        if len(value.players) != SQUAD_SIZE:
            raise ValueError("Current squad must contain exactly 15 players")
        ids = [player.player_id for player in value.players]
        if len(ids) != len(set(ids)):
            raise ValueError("Current squad contains duplicate players")
        if any(
            player.purchase_price <= 0 or player.selling_price <= 0 for player in value.players
        ):
            raise ValueError("Purchase and selling prices must be positive")
        with self.database.session() as session:
            rows = session.execute(
                select(Player.id, Player.position, Team.short_name)
                .join(Team, Player.team_id == Team.id)
                .where(Player.id.in_(ids))
            ).all()
        if len(rows) != SQUAD_SIZE:
            raise ValueError("Current squad contains unknown player IDs")
        positions = Counter(position for _, position, _ in rows)
        if positions != Counter(POSITION_LIMITS):
            raise ValueError("Current squad must have 2 GK, 5 DEF, 5 MID, and 3 FWD")
        teams = Counter(team for _, _, team in rows)
        if any(count > MAX_PER_TEAM for count in teams.values()):
            raise ValueError("Current squad exceeds the three-player club limit")
