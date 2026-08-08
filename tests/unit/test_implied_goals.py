"""Tests for Poisson outcome calculations and implied-goals fitting."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest

from fpl_optimizer.domain.enums import OddsMarket, OddsSelection
from fpl_optimizer.domain.markets import ConsensusMarket
from fpl_optimizer.odds.implied_goals import fit_implied_goals
from fpl_optimizer.odds.poisson import match_probabilities


def consensus(market: OddsMarket, probabilities: dict[OddsSelection, float]) -> ConsensusMarket:
    return ConsensusMarket(
        market,
        probabilities,
        dispersion=0.01,
        bookmaker_count=3,
        observed_at=datetime(2026, 8, 8, tzinfo=UTC),
        devig_method="multiplicative",
    )


def test_poisson_outcomes_sum_to_one() -> None:
    probabilities = match_probabilities(2.1, 0.8)

    assert probabilities.home_win + probabilities.draw + probabilities.away_win == pytest.approx(1)
    assert probabilities.tail_mass < 1e-8


def test_implied_goals_recovers_known_lambdas() -> None:
    known = match_probabilities(2.1, 0.8)
    result = fit_implied_goals(
        consensus(
            OddsMarket.MATCH_RESULT,
            {
                OddsSelection.HOME: known.home_win,
                OddsSelection.DRAW: known.draw,
                OddsSelection.AWAY: known.away_win,
            },
        ),
        consensus(
            OddsMarket.TOTAL_GOALS_2_5,
            {
                OddsSelection.OVER: known.over_2_5,
                OddsSelection.UNDER: 1 - known.over_2_5,
            },
        ),
    )

    assert result.home_xg == pytest.approx(2.1, abs=1e-3)
    assert result.away_xg == pytest.approx(0.8, abs=1e-3)
    assert result.residual < 1e-5


def test_advanced_markets_are_included_in_implied_goal_fit() -> None:
    known = match_probabilities(1.9, 1.2)
    btts = (1 - math.exp(-1.9)) * (1 - math.exp(-1.2))
    home_over = 1 - math.exp(-1.9) * (1 + 1.9)
    away_over = 1 - math.exp(-1.2) * (1 + 1.2)

    result = fit_implied_goals(
        consensus(
            OddsMarket.MATCH_RESULT,
            {
                OddsSelection.HOME: known.home_win,
                OddsSelection.DRAW: known.draw,
                OddsSelection.AWAY: known.away_win,
            },
        ),
        consensus(
            OddsMarket.TOTAL_GOALS_2_5,
            {
                OddsSelection.OVER: known.over_2_5,
                OddsSelection.UNDER: 1 - known.over_2_5,
            },
        ),
        consensus(OddsMarket.BTTS, {OddsSelection.YES: btts, OddsSelection.NO: 1 - btts}),
        consensus(
            OddsMarket.HOME_TOTAL_1_5,
            {OddsSelection.OVER: home_over, OddsSelection.UNDER: 1 - home_over},
        ),
        consensus(
            OddsMarket.AWAY_TOTAL_1_5,
            {OddsSelection.OVER: away_over, OddsSelection.UNDER: 1 - away_over},
        ),
    )

    assert result.home_xg == pytest.approx(1.9, abs=1e-3)
    assert result.away_xg == pytest.approx(1.2, abs=1e-3)
    assert result.btts_yes == pytest.approx(btts, abs=1e-3)
