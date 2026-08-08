"""Persistence and leakage-safe reads for historical forecast evaluation."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fpl_optimizer.database.models import (
    BacktestRun,
    Gameweek,
    Player,
    PlayerForecast,
    PlayerGameweekActual,
    PlayerMarketForecast,
)
from fpl_optimizer.domain.backtesting import (
    BacktestObservation,
    BacktestResult,
    HistoricalOutcomeInput,
)


class BacktestRepository:
    """Store outcomes and assemble strictly pre-deadline forecast observations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def import_outcomes(
        self, outcomes: list[HistoricalOutcomeInput], source_ref: str
    ) -> int:
        """Validate identities and atomically upsert a complete outcome batch."""

        players = {
            row.fpl_id: row
            for row in self.session.scalars(
                select(Player).where(Player.fpl_id.in_([item.player_fpl_id for item in outcomes]))
            )
        }
        gameweeks = {
            row.fpl_id: row
            for row in self.session.scalars(
                select(Gameweek).where(
                    Gameweek.fpl_id.in_([item.gameweek_fpl_id for item in outcomes])
                )
            )
        }
        missing_players = sorted({item.player_fpl_id for item in outcomes} - players.keys())
        missing_gameweeks = sorted({item.gameweek_fpl_id for item in outcomes} - gameweeks.keys())
        if missing_players:
            raise ValueError(f"Unknown official player IDs: {', '.join(map(str, missing_players))}")
        if missing_gameweeks:
            raise ValueError(f"Unknown Gameweeks: {', '.join(map(str, missing_gameweeks))}")
        imported_at = datetime.now(UTC)
        for item in outcomes:
            player_id = players[item.player_fpl_id].id
            gameweek_id = gameweeks[item.gameweek_fpl_id].id
            row = self.session.scalar(
                select(PlayerGameweekActual).where(
                    PlayerGameweekActual.player_id == player_id,
                    PlayerGameweekActual.gameweek_id == gameweek_id,
                )
            )
            if row is None:
                row = PlayerGameweekActual(player_id=player_id, gameweek_id=gameweek_id)
                self.session.add(row)
            row.actual_points = item.actual_points
            row.actual_minutes = item.actual_minutes
            row.goals = item.goals
            row.assists = item.assists
            row.clean_sheets = item.clean_sheets
            row.saves = item.saves
            row.bonus = item.bonus
            row.finalized_at = item.finalized_at or imported_at
            row.imported_at = imported_at
            row.source_ref = source_ref
        self.session.flush()
        return len(outcomes)

    def outcome_count(self) -> int:
        """Count available player/Gameweek outcomes."""

        return int(self.session.scalar(select(func.count(PlayerGameweekActual.id))) or 0)

    def observations(self) -> list[BacktestObservation]:
        """Pair outcomes with the latest forecast that existed by each deadline."""

        actual_rows = list(
            self.session.execute(
                select(PlayerGameweekActual, Player, Gameweek)
                .join(Player, PlayerGameweekActual.player_id == Player.id)
                .join(Gameweek, PlayerGameweekActual.gameweek_id == Gameweek.id)
                .order_by(Gameweek.fpl_id, Player.id)
            )
        )
        observations: list[BacktestObservation] = []
        for actual, player, gameweek in actual_rows:
            statistical = self.session.scalar(
                select(PlayerForecast)
                .where(
                    PlayerForecast.player_id == player.id,
                    PlayerForecast.gameweek_id == gameweek.id,
                    PlayerForecast.prediction_at <= gameweek.deadline_at,
                    PlayerForecast.input_cutoff_at <= gameweek.deadline_at,
                )
                .order_by(PlayerForecast.prediction_at.desc(), PlayerForecast.id.desc())
                .limit(1)
            )
            if statistical is None:
                continue
            market = self.session.scalar(
                select(PlayerMarketForecast)
                .where(
                    PlayerMarketForecast.player_id == player.id,
                    PlayerMarketForecast.gameweek_id == gameweek.id,
                    PlayerMarketForecast.prediction_at <= gameweek.deadline_at,
                    PlayerMarketForecast.input_cutoff_at <= gameweek.deadline_at,
                )
                .order_by(
                    PlayerMarketForecast.prediction_at.desc(),
                    PlayerMarketForecast.id.desc(),
                )
                .limit(1)
            )
            observations.append(
                BacktestObservation(
                    player_id=player.id,
                    player=player.web_name,
                    position=player.position,
                    gameweek_id=gameweek.fpl_id,
                    gameweek=gameweek.name,
                    stat_xpts=statistical.stat_xpts,
                    market_xpts=market.market_xpts if market else None,
                    actual_points=actual.actual_points,
                    expected_minutes=statistical.expected_minutes,
                    actual_minutes=actual.actual_minutes,
                    prediction_at=statistical.prediction_at,
                )
            )
        return observations

    def save(self, result: BacktestResult, created_at: datetime) -> BacktestRun:
        """Persist a complete reproducible result payload."""

        row = BacktestRun(
            created_at=created_at,
            observation_count=result.observations,
            gameweek_count=result.gameweeks,
            evaluation_mode=result.evaluation_mode,
            selected_market_weight=result.selected_market_weight,
            statistical_rmse=result.statistical.rmse,
            selected_blend_rmse=result.selected_blend.rmse,
            result_json=json.dumps(asdict(result), sort_keys=True),
        )
        self.session.add(row)
        self.session.flush()
        return row

    def recent(self, limit: int = 10) -> list[dict[str, object]]:
        """Return compact recent calibration runs."""

        rows = self.session.scalars(
            select(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(limit)
        )
        return [
            {
                "Run ID": row.id,
                "Created": row.created_at,
                "Observations": row.observation_count,
                "Gameweeks": row.gameweek_count,
                "Evaluation": row.evaluation_mode,
                "Suggested market influence": row.selected_market_weight,
                "Stat RMSE": row.statistical_rmse,
                "Blend RMSE": row.selected_blend_rmse,
            }
            for row in rows
        ]
