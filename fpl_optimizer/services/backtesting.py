"""Application service for outcome imports and forecast calibration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fpl_optimizer.backtesting.calibration import evaluate_backtest
from fpl_optimizer.backtesting.outcomes import parse_outcomes_csv
from fpl_optimizer.database.backtest_repository import BacktestRepository
from fpl_optimizer.database.base import Database
from fpl_optimizer.domain.backtesting import BacktestResult


@dataclass(frozen=True, slots=True)
class BacktestRunReport:
    """Persisted backtest result and identity."""

    run_id: int
    created_at: datetime
    result: BacktestResult


class BacktestService:
    """Coordinate atomic outcome imports and leakage-safe historical evaluation."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def import_csv(self, content: str, source_ref: str = "CSV upload") -> int:
        """Parse and atomically persist historical outcome rows."""

        outcomes = parse_outcomes_csv(content)
        with self.database.session() as session:
            return BacktestRepository(session).import_outcomes(outcomes, source_ref)

    def outcome_count(self) -> int:
        """Return the number of imported outcomes."""

        with self.database.session() as session:
            return BacktestRepository(session).outcome_count()

    def run(self) -> BacktestRunReport:
        """Evaluate all outcome-matched, pre-deadline forecasts and save the report."""

        with self.database.session() as session:
            observations = BacktestRepository(session).observations()
        result = evaluate_backtest(observations)
        created_at = datetime.now(UTC)
        with self.database.session() as session:
            row = BacktestRepository(session).save(result, created_at)
            run_id = row.id
        return BacktestRunReport(run_id, created_at, result)

    def recent(self) -> list[dict[str, object]]:
        """Return recent historical evaluations."""

        with self.database.session() as session:
            return BacktestRepository(session).recent()
