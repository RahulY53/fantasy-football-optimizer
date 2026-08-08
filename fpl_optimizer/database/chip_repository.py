"""Persistence for reproducible chip evaluations."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpl_optimizer.database.models import ChipRun
from fpl_optimizer.domain.chips import ChipEvaluation
from fpl_optimizer.domain.strategy import StrategyProfile


class ChipRepository:
    """Store complete Phase 11 chip evaluations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(
        self,
        *,
        team_id: int,
        evaluation: ChipEvaluation,
        strategy: StrategyProfile,
        market_weight: float,
        forecast_at: datetime,
        created_at: datetime,
    ) -> ChipRun:
        """Persist one four-chip comparison."""

        row = ChipRun(
            user_team_id=team_id,
            created_at=created_at,
            forecast_at=forecast_at,
            horizon=evaluation.horizon,
            market_weight=market_weight,
            budget=evaluation.budget,
            best_chip=evaluation.best_chip,
            best_gain=evaluation.best_gain,
            strategy_json=json.dumps(asdict(strategy), sort_keys=True),
            result_json=json.dumps(asdict(evaluation), sort_keys=True),
        )
        self.session.add(row)
        self.session.flush()
        return row

    def recent(self, limit: int = 10) -> list[dict[str, object]]:
        """Return compact recent chip evaluations."""

        rows = self.session.scalars(
            select(ChipRun).order_by(ChipRun.created_at.desc()).limit(limit)
        )
        return [
            {
                "Run ID": row.id,
                "Created": row.created_at,
                "Forecasted": row.forecast_at,
                "Horizon": row.horizon,
                "Market influence": row.market_weight,
                "Budget": row.budget,
                "Best chip": row.best_chip or "None available",
                "Projected gain": row.best_gain,
            }
            for row in rows
        ]

