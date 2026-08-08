"""Persistence for reproducible transfer comparisons."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpl_optimizer.database.models import TransferPlan
from fpl_optimizer.domain.strategy import StrategyProfile
from fpl_optimizer.domain.transfers import TransferEvaluation


class TransferRepository:
    """Store full transfer inputs, alternatives, and recommendations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(
        self,
        *,
        team_id: int,
        evaluation: TransferEvaluation,
        strategy: StrategyProfile,
        market_weight: float,
        forecast_at: datetime,
        created_at: datetime,
    ) -> TransferPlan:
        """Persist one complete Phase 7 evaluation."""

        row = TransferPlan(
            user_team_id=team_id,
            created_at=created_at,
            forecast_at=forecast_at,
            horizon=evaluation.horizon,
            market_weight=market_weight,
            free_transfers=evaluation.free_transfers,
            bank=evaluation.starting_bank,
            transfer_reluctance=strategy.transfer_reluctance,
            recommendation=evaluation.recommendation,
            strategy_json=json.dumps(asdict(strategy), sort_keys=True),
            evaluation_json=json.dumps(asdict(evaluation), sort_keys=True),
        )
        self.session.add(row)
        self.session.flush()
        return row

    def recent(self, limit: int = 10) -> list[dict[str, object]]:
        """Return compact recent transfer-run summaries."""

        rows = self.session.scalars(
            select(TransferPlan).order_by(TransferPlan.created_at.desc()).limit(limit)
        )
        return [
            {
                "Run ID": row.id,
                "Created": row.created_at,
                "Forecasted": row.forecast_at,
                "Horizon": row.horizon,
                "Free transfers": row.free_transfers,
                "Bank": row.bank,
                "Reluctance": row.transfer_reluctance,
                "Recommendation": row.recommendation,
            }
            for row in rows
        ]
