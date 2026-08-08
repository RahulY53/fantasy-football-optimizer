"""Tests for historical outcome parsing and blend calibration."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fpl_optimizer.backtesting.calibration import evaluate_backtest
from fpl_optimizer.backtesting.outcomes import parse_outcomes_csv
from fpl_optimizer.domain.backtesting import BacktestObservation


def test_outcome_csv_parser_is_strict_and_complete() -> None:
    content = (
        "player_id,gameweek,actual_points,actual_minutes,finalized_at\n"
        "10,1,7,90,2026-08-18T22:00:00Z\n"
    )

    result = parse_outcomes_csv(content)

    assert result[0].player_fpl_id == 10
    assert result[0].actual_minutes == 90
    assert result[0].finalized_at == datetime(2026, 8, 18, 22, tzinfo=UTC)


def test_outcome_csv_rejects_duplicate_rows() -> None:
    content = "player_id,gameweek,actual_points\n10,1,7\n10,1,5\n"

    with pytest.raises(ValueError, match="duplicate"):
        parse_outcomes_csv(content)


def test_backtest_uses_earlier_gameweeks_to_select_blend() -> None:
    observations = [
        BacktestObservation(
            player_id=gameweek,
            player=f"Player {gameweek}",
            position=("GKP", "DEF", "MID", "FWD")[gameweek - 1],
            gameweek_id=gameweek,
            gameweek=f"Gameweek {gameweek}",
            stat_xpts=2.0,
            market_xpts=6.0,
            actual_points=6.0,
            expected_minutes=80.0,
            actual_minutes=90,
            prediction_at=datetime(2026, 8, gameweek, tzinfo=UTC),
        )
        for gameweek in range(1, 5)
    ]

    result = evaluate_backtest(observations)

    assert result.evaluation_mode == "chronological holdout"
    assert result.calibration_gameweeks == ("Gameweek 1", "Gameweek 2")
    assert result.evaluation_gameweeks == ("Gameweek 3", "Gameweek 4")
    assert result.selected_market_weight == 1.0
    assert result.selected_blend.rmse == 0
    assert result.statistical.bias == -4
    assert result.expected_minutes is not None
    assert result.expected_minutes.mae == 10
