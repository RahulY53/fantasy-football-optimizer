"""Fit market-implied home and away Poisson goal means."""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import least_squares  # type: ignore[import-untyped]

from fpl_optimizer.domain.enums import OddsSelection
from fpl_optimizer.domain.markets import ConsensusMarket, ImpliedGoals
from fpl_optimizer.odds.poisson import match_probabilities


def fit_implied_goals(
    match_result: ConsensusMarket,
    totals: ConsensusMarket,
    btts: ConsensusMarket | None = None,
    home_total: ConsensusMarket | None = None,
    away_total: ConsensusMarket | None = None,
) -> ImpliedGoals:
    """Fit positive team goal means to core and optional advanced market probabilities."""

    targets = [
        match_result.probabilities[OddsSelection.HOME],
        match_result.probabilities[OddsSelection.DRAW],
        match_result.probabilities[OddsSelection.AWAY],
        totals.probabilities[OddsSelection.OVER],
    ]
    if btts is not None:
        targets.append(btts.probabilities[OddsSelection.YES])
    if home_total is not None:
        targets.append(home_total.probabilities[OddsSelection.OVER])
    if away_total is not None:
        targets.append(away_total.probabilities[OddsSelection.OVER])
    target_array = np.array(targets)

    def residuals(theta: np.ndarray) -> np.ndarray:
        probabilities = match_probabilities(math.exp(theta[0]), math.exp(theta[1]))
        home_xg = math.exp(theta[0])
        away_xg = math.exp(theta[1])
        model = [
            probabilities.home_win,
            probabilities.draw,
            probabilities.away_win,
            probabilities.over_2_5,
        ]
        if btts is not None:
            model.append(_btts(home_xg, away_xg))
        if home_total is not None:
            model.append(_over_1_5(home_xg))
        if away_total is not None:
            model.append(_over_1_5(away_xg))
        return np.array(model) - target_array  # type: ignore[no-any-return]

    best = None
    for initial in ((1.5, 1.1), (2.2, 0.8), (0.9, 1.8), (1.2, 1.2)):
        result = least_squares(
            residuals,
            x0=np.log(initial),
            bounds=(np.log((0.05, 0.05)), np.log((5.0, 5.0))),
        )
        if best is None or sum(result.fun**2) < sum(best.fun**2):
            best = result
    assert best is not None
    home_xg, away_xg = (math.exp(float(value)) for value in best.x)
    probabilities = match_probabilities(home_xg, away_xg)
    return ImpliedGoals(
        home_xg=home_xg,
        away_xg=away_xg,
        home_win=probabilities.home_win,
        draw=probabilities.draw,
        away_win=probabilities.away_win,
        over_2_5=probabilities.over_2_5,
        btts_yes=_btts(home_xg, away_xg),
        home_over_1_5=_over_1_5(home_xg),
        away_over_1_5=_over_1_5(away_xg),
        residual=float(math.sqrt(sum(best.fun**2))),
        success=bool(best.success),
    )


def _btts(home_xg: float, away_xg: float) -> float:
    return (1.0 - math.exp(-home_xg)) * (1.0 - math.exp(-away_xg))


def _over_1_5(xg: float) -> float:
    return 1.0 - math.exp(-xg) * (1.0 + xg)
