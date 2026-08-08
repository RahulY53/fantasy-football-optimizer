"""Mathematical tests for bookmaker margin removal."""

from __future__ import annotations

import pytest

from fpl_optimizer.domain.enums import OddsSelection
from fpl_optimizer.odds.devig import DevigError, devig

PRICES = {
    OddsSelection.HOME: 2.0,
    OddsSelection.DRAW: 3.5,
    OddsSelection.AWAY: 4.0,
}


@pytest.mark.parametrize("method", ["multiplicative", "power", "shin"])
def test_devig_methods_return_fair_probability_vector(method: str) -> None:
    fair = devig(PRICES, method)

    assert sum(fair.probabilities.values()) == pytest.approx(1.0)
    assert fair.overround == pytest.approx(sum(1 / price for price in PRICES.values()))
    assert all(0 < probability < 1 for probability in fair.probabilities.values())


def test_devig_rejects_invalid_market() -> None:
    with pytest.raises(DevigError):
        devig({OddsSelection.HOME: 1.0, OddsSelection.AWAY: 2.0})
