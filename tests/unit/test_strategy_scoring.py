"""Tests for weight normalization and explainable strategy scores."""

from __future__ import annotations

import pytest

from fpl_optimizer.domain.strategy import PlayerStrategyInput, StrategyProfile
from fpl_optimizer.scoring.normalization import normalize_weights, percentile_scores
from fpl_optimizer.scoring.optimization_score import score_players, strategy_summary


def player(player_id: int, name: str, xpts: float, ownership: float) -> PlayerStrategyInput:
    """Build a compact strategy input for deterministic unit tests."""

    return PlayerStrategyInput(
        player_id=player_id,
        player=name,
        position="MID",
        team="TST",
        price=8.0,
        ownership=ownership,
        form=xpts / 2,
        status="a",
        chance_next_round=None,
        horizon_xpts=xpts,
        week_xpts=(xpts / 3, xpts / 3, xpts / 3),
        expected_minutes=85,
        fixture_quality=3,
        attacking_xpts=xpts / 2,
        clean_sheet_xpts=1,
        bonus_xpts=0.5,
        confidence=1.0,
    )


def profile(**overrides: object) -> StrategyProfile:
    """Build a simple custom profile."""

    values: dict[str, object] = {
        "name": "Test",
        "mode": "simple",
        "preset": "Custom",
        "horizon": 3,
        "risk_appetite": 40,
        "transfer_reluctance": 50,
        "ownership_preference": 0,
        "weights": {"expected_points": 100, "value": 50},
    }
    values.update(overrides)
    return StrategyProfile(**values)  # type: ignore[arg-type]


def test_percentiles_handle_ties_and_weights_normalize() -> None:
    assert percentile_scores([1, 2, 2, 4]) == pytest.approx([0, 50, 50, 100])
    assert percentile_scores([7, 7]) == [50, 50]
    assert normalize_weights({"a": 80, "b": 20, "ignored": 0}) == {
        "a": 0.8,
        "b": 0.2,
    }


def test_score_is_ranked_and_exactly_decomposable() -> None:
    scores = score_players(
        [player(1, "Low", 6, 20), player(2, "Mid", 12, 15), player(3, "High", 18, 40)],
        profile(),
    )

    assert [score.player for score in scores] == ["High", "Mid", "Low"]
    assert all(
        score.score == pytest.approx(sum(item.contribution for item in score.contributions))
        for score in scores
    )
    assert all(0 <= score.score <= 100 for score in scores)


def test_negative_ownership_preference_rewards_differentials() -> None:
    players = [player(1, "Template", 10, 60), player(2, "Differential", 10, 2)]
    scores = score_players(
        players,
        profile(weights={"expected_points": 1}, ownership_preference=-100),
    )

    assert scores[0].player == "Differential"
    ownership = next(
        item for item in scores[0].contributions if item.feature == "ownership_fit"
    )
    assert ownership.percentile == 100


def test_profile_validation_and_programmatic_summary() -> None:
    with pytest.raises(ValueError, match="At least one"):
        score_players([player(1, "One", 10, 5)], profile(weights={"value": 0}))
    summary = strategy_summary(
        profile(weights={"expected_points": 90, "value": 50, "differential": 10})
    )
    assert "expected points" in summary
    assert "differential potential" in summary
