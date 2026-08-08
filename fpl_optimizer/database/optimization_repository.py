"""Persistence for reproducible optimization runs."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpl_optimizer.database.models import OptimizationRun
from fpl_optimizer.domain.optimizer import SquadOptimizationRequest, SquadOptimizationResult
from fpl_optimizer.domain.strategy import StrategyProfile


class OptimizationRepository:
    """Store immutable solver inputs and selected squads."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(
        self,
        *,
        result: SquadOptimizationResult,
        request: SquadOptimizationRequest,
        strategy: StrategyProfile,
        market_weight: float,
        created_at: datetime,
    ) -> OptimizationRun:
        """Persist one successful optimization run."""

        row = OptimizationRun(
            created_at=created_at,
            optimizer_type="initial-squad",
            solver=result.solver,
            status=result.status,
            budget=result.budget,
            total_cost=result.total_cost,
            objective_score=result.objective_score,
            total_xpts=result.total_xpts,
            market_weight=market_weight,
            strategy_json=json.dumps(asdict(strategy), sort_keys=True),
            constraints_json=json.dumps(asdict(request), sort_keys=True),
            result_json=json.dumps(asdict(result), sort_keys=True),
        )
        self.session.add(row)
        self.session.flush()
        return row

    def recent(self, limit: int = 10) -> list[dict[str, object]]:
        """Return compact recent-run summaries."""

        rows = self.session.scalars(
            select(OptimizationRun).order_by(OptimizationRun.created_at.desc()).limit(limit)
        )
        return [
            {
                "Run ID": row.id,
                "Created": row.created_at,
                "Status": row.status,
                "Solver": row.solver,
                "Budget": row.budget,
                "Cost": row.total_cost,
                "Objective": row.objective_score,
                "Projected xPts": row.total_xpts,
            }
            for row in rows
        ]

    def latest_squad_player_ids(self) -> tuple[int, ...]:
        """Return selected player IDs from the most recent initial-squad run."""

        row = self.session.scalar(
            select(OptimizationRun)
            .where(OptimizationRun.optimizer_type == "initial-squad")
            .order_by(OptimizationRun.created_at.desc())
            .limit(1)
        )
        if row is None:
            return ()
        result = json.loads(row.result_json)
        return tuple(int(player["player_id"]) for player in result["players"])
