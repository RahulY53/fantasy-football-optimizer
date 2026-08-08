"""Persistence for reproducible multi-Gameweek plans."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpl_optimizer.database.models import PlannerRun
from fpl_optimizer.domain.planner import MultiGameweekPlan
from fpl_optimizer.domain.strategy import StrategyProfile


class PlannerRepository:
    """Store full Phase 8 inputs and optimized paths."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(
        self,
        *,
        team_id: int,
        plan: MultiGameweekPlan,
        strategy: StrategyProfile,
        market_weight: float,
        forecast_at: datetime,
        created_at: datetime,
    ) -> PlannerRun:
        """Persist one complete multi-period result."""

        row = PlannerRun(
            user_team_id=team_id,
            created_at=created_at,
            forecast_at=forecast_at,
            horizon=plan.horizon,
            market_weight=market_weight,
            starting_free_transfers=plan.starting_free_transfers,
            starting_bank=plan.starting_bank,
            total_transfers=plan.total_transfers,
            total_hits=plan.total_hits,
            net_projected_points=plan.net_projected_points,
            strategy_json=json.dumps(asdict(strategy), sort_keys=True),
            result_json=json.dumps(asdict(plan), sort_keys=True),
        )
        self.session.add(row)
        self.session.flush()
        return row

    def recent(self, limit: int = 10) -> list[dict[str, object]]:
        """Return compact recent planning-run summaries."""

        rows = self.session.scalars(
            select(PlannerRun).order_by(PlannerRun.created_at.desc()).limit(limit)
        )
        return [
            {
                "Run ID": row.id,
                "Created": row.created_at,
                "Forecasted": row.forecast_at,
                "Horizon": row.horizon,
                "Starting free transfers": row.starting_free_transfers,
                "Starting bank": row.starting_bank,
                "Transfers": row.total_transfers,
                "Hits": row.total_hits,
                "Net projected points": row.net_projected_points,
            }
            for row in rows
        ]

