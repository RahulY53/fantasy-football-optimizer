"""Read-only orchestration for model diagnostics and explainability."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from fpl_optimizer.config import Settings
from fpl_optimizer.database.backtest_repository import BacktestRepository
from fpl_optimizer.database.base import Database
from fpl_optimizer.database.model_lab_repository import ModelLabRepository
from fpl_optimizer.domain.model_lab import FeatureInfluence, ModelLabReport
from fpl_optimizer.domain.strategy import PlayerStrategyScore, ScoreContribution, StrategyProfile
from fpl_optimizer.services.strategy import StrategyService


class ModelLabService:
    """Build diagnostics exclusively from cached, already-computed artifacts."""

    def __init__(
        self, database: Database, strategy: StrategyService, settings: Settings
    ) -> None:
        self.database = database
        self.strategy = strategy
        self.settings = settings

    def report(self, profile: StrategyProfile, market_weight: float) -> ModelLabReport:
        """Return a read-only snapshot; never run forecasting or optimization."""

        with self.database.session() as session:
            repository = ModelLabRepository(session)
            diagnostics = repository.diagnostics(market_weight)
            versions = repository.versions()
            forecast_at = repository.latest_forecast_at()
            market_at = repository.latest_market_forecast_at()
            latest_backtest = repository.latest_backtest()
            recent = tuple(BacktestRepository(session).recent())
        scores = self.strategy.score(profile, market_weight) if diagnostics else []
        return ModelLabReport(
            generated_at=datetime.now(UTC),
            forecast_at=forecast_at,
            market_forecast_at=market_at,
            market_weight=market_weight,
            diagnostics=diagnostics,
            versions=versions,
            feature_influence=summarize_feature_influence(scores),
            recent_backtests=recent,
            latest_backtest=latest_backtest,
            safe_settings=(
                ("Forecast horizon", "Up to 6 Gameweeks"),
                ("Default market influence", "30%"),
                ("Odds provider", self.settings.odds_provider),
                (
                    "Odds integration",
                    "Configured" if self.settings.odds_api_key else "Not configured",
                ),
                ("FPL scoring", "2026/27"),
                ("Runtime log level", self.settings.log_level),
            ),
        )


def summarize_feature_influence(
    scores: list[PlayerStrategyScore],
) -> tuple[FeatureInfluence, ...]:
    """Aggregate decomposed player scores into a global feature view."""

    if not scores:
        return ()
    grouped: dict[str, list[tuple[str, ScoreContribution]]] = defaultdict(list)
    for score in scores:
        for contribution in score.contributions:
            grouped[contribution.feature].append((score.player, contribution))
    output: list[FeatureInfluence] = []
    for feature, rows in grouped.items():
        top_player, top = max(rows, key=lambda row: row[1].contribution)
        sample = rows[0][1]
        output.append(
            FeatureInfluence(
                feature=feature,
                label=sample.label,
                raw_weight=sample.raw_weight,
                normalized_weight=sample.normalized_weight,
                mean_contribution=sum(row[1].contribution for row in rows) / len(rows),
                top_player=top_player,
                top_contribution=top.contribution,
            )
        )
    return tuple(sorted(output, key=lambda row: (-row.mean_contribution, row.label)))
