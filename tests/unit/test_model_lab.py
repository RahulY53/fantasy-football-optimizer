"""Regression tests for Model Lab aggregation and safe metadata."""

from fpl_optimizer.domain.strategy import PlayerStrategyScore, ScoreContribution
from fpl_optimizer.services.model_lab import summarize_feature_influence


def test_feature_influence_aggregates_decomposed_strategy_scores() -> None:
    scores = [
        PlayerStrategyScore(
            player_id=index,
            player=player,
            position="MID",
            team="TST",
            price=7.0,
            ownership=10.0,
            horizon_xpts=20.0,
            value=3.0,
            risk=20.0,
            score=contribution,
            contributions=(
                ScoreContribution(
                    feature="expected_points",
                    label="Expected points",
                    raw_value=20.0,
                    percentile=contribution * 2,
                    raw_weight=80.0,
                    normalized_weight=0.5,
                    contribution=contribution,
                ),
            ),
        )
        for index, (player, contribution) in enumerate(
            (("First Player", 40.0), ("Second Player", 20.0)), start=1
        )
    ]

    result = summarize_feature_influence(scores)

    assert len(result) == 1
    assert result[0].mean_contribution == 30.0
    assert result[0].top_player == "First Player"
    assert result[0].normalized_weight == 0.5

