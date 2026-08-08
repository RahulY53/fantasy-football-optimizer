"""End-to-end persisted initial-squad optimization test."""

from __future__ import annotations

from fpl_optimizer.database.base import Database
from fpl_optimizer.domain.optimizer import SquadOptimizationRequest
from fpl_optimizer.domain.strategy import PlayerStrategyScore, StrategyProfile
from fpl_optimizer.services.optimizer import SquadOptimizerService


class RecordedStrategyService:
    """Small deterministic score provider for optimizer integration testing."""

    def __init__(self, scores: list[PlayerStrategyScore]) -> None:
        self.scores = scores

    def score(
        self, _: StrategyProfile, market_weight: float
    ) -> list[PlayerStrategyScore]:
        assert market_weight == 0.3
        return self.scores


def test_optimizer_service_persists_reproducible_run(tmp_path) -> None:
    database = Database(f"sqlite:///{tmp_path / 'optimizer.db'}")
    database.create_schema()
    scores: list[PlayerStrategyScore] = []
    player_id = 1
    for position, count, price in (
        ("GK", 4, 4.0),
        ("DEF", 10, 4.0),
        ("MID", 10, 5.0),
        ("FWD", 6, 5.5),
    ):
        for index in range(count):
            scores.append(
                PlayerStrategyScore(
                    player_id=player_id,
                    player=f"{position} {index}",
                    position=position,
                    team=f"T{index % 10}",
                    price=price + index * 0.1,
                    ownership=float(index),
                    horizon_xpts=6.0 + index,
                    value=1.0,
                    risk=20.0,
                    score=50.0 + index,
                    contributions=(),
                )
            )
            player_id += 1
    strategy = StrategyProfile(
        name="Integration",
        mode="simple",
        preset="Custom",
        horizon=3,
        risk_appetite=40,
        transfer_reluctance=50,
        ownership_preference=0,
        weights={"expected_points": 100},
    )
    service = SquadOptimizerService(
        database,
        RecordedStrategyService(scores),  # type: ignore[arg-type]
    )

    report = service.run(strategy, 0.3, SquadOptimizationRequest(budget=100.0))
    recent = service.recent()

    assert report.run_id > 0
    assert report.result.status == "Optimal"
    assert len(report.result.players) == 15
    assert recent[0]["Run ID"] == report.run_id
    assert recent[0]["Projected xPts"] == report.result.total_xpts
    database.engine.dispose()
