"""Persistence for reproducible Monte Carlo results."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpl_optimizer.database.models import SimulationRun
from fpl_optimizer.domain.simulation import SimulationResult


class SimulationRepository:
    """Store full Phase 10 simulation outputs."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(
        self,
        *,
        team_id: int,
        result: SimulationResult,
        market_weight: float,
        forecast_at: datetime,
        created_at: datetime,
    ) -> SimulationRun:
        """Persist one complete Monte Carlo result."""

        row = SimulationRun(
            user_team_id=team_id,
            created_at=created_at,
            forecast_at=forecast_at,
            horizon=result.horizon,
            iterations=result.iterations,
            seed=result.seed,
            market_weight=market_weight,
            mean_points=result.mean,
            median_points=result.median,
            p10_points=result.p10,
            p90_points=result.p90,
            result_json=json.dumps(asdict(result), sort_keys=True),
        )
        self.session.add(row)
        self.session.flush()
        return row

    def recent(self, limit: int = 10) -> list[dict[str, object]]:
        """Return compact recent simulation summaries."""

        rows = self.session.scalars(
            select(SimulationRun).order_by(SimulationRun.created_at.desc()).limit(limit)
        )
        return [
            {
                "Run ID": row.id,
                "Created": row.created_at,
                "Forecasted": row.forecast_at,
                "Horizon": row.horizon,
                "Iterations": row.iterations,
                "Seed": row.seed,
                "Market influence": row.market_weight,
                "Mean": row.mean_points,
                "Median": row.median_points,
                "P10": row.p10_points,
                "P90": row.p90_points,
            }
            for row in rows
        ]

