"""Manual-entry odds provider."""

from __future__ import annotations

from datetime import datetime

from fpl_optimizer.domain.enums import OddsMarket, OddsSelection, OddsSnapshotKind
from fpl_optimizer.domain.markets import GoalscorerOddsQuote, OddsQuote


class ManualOddsProvider:
    """Build a complete MVP market snapshot from validated form values."""

    name = "manual"

    def __init__(
        self,
        fixture_fpl_id: int,
        bookmaker: str,
        observed_at: datetime,
        home: float,
        draw: float,
        away: float,
        over_2_5: float,
        under_2_5: float,
        btts_yes: float | None = None,
        btts_no: float | None = None,
        home_over_1_5: float | None = None,
        home_under_1_5: float | None = None,
        away_over_1_5: float | None = None,
        away_under_1_5: float | None = None,
    ) -> None:
        prices = (home, draw, away, over_2_5, under_2_5)
        if any(price <= 1.0 for price in prices):
            raise ValueError("All decimal odds must be greater than 1")
        if not bookmaker.strip():
            raise ValueError("Bookmaker cannot be blank")
        self._quotes = [
            OddsQuote(
                fixture_fpl_id,
                "manual",
                bookmaker.strip(),
                OddsMarket.MATCH_RESULT,
                selection,
                price,
                observed_at,
                OddsSnapshotKind.CURRENT,
                "manual-entry",
            )
            for selection, price in (
                (OddsSelection.HOME, home),
                (OddsSelection.DRAW, draw),
                (OddsSelection.AWAY, away),
            )
        ] + [
            OddsQuote(
                fixture_fpl_id,
                "manual",
                bookmaker.strip(),
                OddsMarket.TOTAL_GOALS_2_5,
                selection,
                price,
                observed_at,
                OddsSnapshotKind.CURRENT,
                "manual-entry",
            )
            for selection, price in (
                (OddsSelection.OVER, over_2_5),
                (OddsSelection.UNDER, under_2_5),
            )
        ]
        optional_markets = (
            (OddsMarket.BTTS, btts_yes, btts_no, OddsSelection.YES, OddsSelection.NO),
            (
                OddsMarket.HOME_TOTAL_1_5,
                home_over_1_5,
                home_under_1_5,
                OddsSelection.OVER,
                OddsSelection.UNDER,
            ),
            (
                OddsMarket.AWAY_TOTAL_1_5,
                away_over_1_5,
                away_under_1_5,
                OddsSelection.OVER,
                OddsSelection.UNDER,
            ),
        )
        for market, first, second, first_selection, second_selection in optional_markets:
            if first is None and second is None:
                continue
            if first is None or second is None or first <= 1.0 or second <= 1.0:
                raise ValueError(f"{market.value} requires two decimal odds greater than 1")
            self._quotes.extend(
                OddsQuote(
                    fixture_fpl_id,
                    "manual",
                    bookmaker.strip(),
                    market,
                    selection,
                    price,
                    observed_at,
                    OddsSnapshotKind.CURRENT,
                    "manual-entry",
                )
                for selection, price in (
                    (first_selection, first),
                    (second_selection, second),
                )
            )

    def get_quotes(self) -> list[OddsQuote | GoalscorerOddsQuote]:
        """Return the complete manual snapshot."""

        return list(self._quotes)
