"""Bookmaker margin-removal methods."""

from __future__ import annotations

import math
from collections.abc import Mapping

from scipy.optimize import brentq  # type: ignore[import-untyped]

from fpl_optimizer.domain.enums import OddsSelection
from fpl_optimizer.domain.markets import FairMarket


class DevigError(ValueError):
    """Raised for invalid odds or a failed numerical margin removal."""


def devig(
    decimal_odds: Mapping[OddsSelection, float], method: str = "multiplicative"
) -> FairMarket:
    """Convert a complete mutually exclusive market into fair probabilities."""

    if len(decimal_odds) < 2 or any(price <= 1.0 for price in decimal_odds.values()):
        raise DevigError("A market requires at least two decimal odds greater than 1")
    raw = {selection: 1.0 / price for selection, price in decimal_odds.items()}
    overround = sum(raw.values())
    if overround <= 1.0:
        raise DevigError("Market overround must be greater than 1")

    if method == "multiplicative":
        probabilities = {selection: value / overround for selection, value in raw.items()}
        return FairMarket(probabilities, overround, method)
    if method == "power":
        exponent = brentq(lambda k: sum(value**k for value in raw.values()) - 1.0, 0.01, 100)
        probabilities = {selection: value**exponent for selection, value in raw.items()}
        return FairMarket(_normalize(probabilities), overround, method, exponent)
    if method == "shin":
        z = _shin_parameter(list(raw.values()), overround)
        probabilities = {
            selection: (math.sqrt(z * z + 4.0 * (1.0 - z) * value * value / overround) - z)
            / (2.0 * (1.0 - z))
            for selection, value in raw.items()
        }
        return FairMarket(_normalize(probabilities), overround, method, z)
    raise DevigError(f"Unknown de-vig method: {method}")


def _shin_parameter(raw: list[float], overround: float) -> float:
    def total(z: float) -> float:
        return sum(
            (math.sqrt(z * z + 4.0 * (1.0 - z) * value * value / overround) - z) / (2.0 * (1.0 - z))
            for value in raw
        )

    try:
        return float(brentq(lambda value: total(value) - 1.0, 0.0, 0.99))
    except ValueError as error:
        raise DevigError("Shin method did not converge for this market") from error


def _normalize(values: Mapping[OddsSelection, float]) -> dict[OddsSelection, float]:
    total = sum(values.values())
    return {selection: value / total for selection, value in values.items()}
