"""Consensus probabilities across bookmaker snapshots."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime

from fpl_optimizer.domain.enums import OddsMarket, OddsSelection
from fpl_optimizer.domain.markets import ConsensusMarket, OddsQuote
from fpl_optimizer.odds.devig import DevigError, devig

REQUIRED_SELECTIONS = {
    OddsMarket.MATCH_RESULT: {
        OddsSelection.HOME,
        OddsSelection.DRAW,
        OddsSelection.AWAY,
    },
    OddsMarket.TOTAL_GOALS_2_5: {OddsSelection.OVER, OddsSelection.UNDER},
    OddsMarket.BTTS: {OddsSelection.YES, OddsSelection.NO},
    OddsMarket.HOME_TOTAL_1_5: {OddsSelection.OVER, OddsSelection.UNDER},
    OddsMarket.AWAY_TOTAL_1_5: {OddsSelection.OVER, OddsSelection.UNDER},
}


def build_consensus(
    quotes: list[OddsQuote], market: OddsMarket, method: str = "multiplicative"
) -> ConsensusMarket:
    """De-vig complete books independently, then aggregate fair probabilities."""

    by_bookmaker: dict[str, list[OddsQuote]] = defaultdict(list)
    for quote in quotes:
        if quote.market is market:
            by_bookmaker[quote.bookmaker].append(quote)

    fair_books: list[dict[OddsSelection, float]] = []
    observed: list[datetime] = []
    for bookmaker_quotes in by_bookmaker.values():
        latest: dict[OddsSelection, OddsQuote] = {}
        for quote in bookmaker_quotes:
            if (
                quote.selection not in latest
                or quote.observed_at > latest[quote.selection].observed_at
            ):
                latest[quote.selection] = quote
        if set(latest) != REQUIRED_SELECTIONS[market]:
            continue
        try:
            fair = devig(
                {selection: quote.decimal_odds for selection, quote in latest.items()},
                method,
            )
        except DevigError:
            continue
        fair_books.append(fair.probabilities)
        observed.extend(quote.observed_at for quote in latest.values())

    if not fair_books:
        raise ValueError(f"No complete bookmaker snapshots for {market.value}")
    selections = REQUIRED_SELECTIONS[market]
    medians = {
        selection: statistics.median(book[selection] for book in fair_books)
        for selection in selections
    }
    total = sum(medians.values())
    consensus = {selection: value / total for selection, value in medians.items()}
    absolute_deviations = [
        abs(book[selection] - consensus[selection])
        for book in fair_books
        for selection in selections
    ]
    return ConsensusMarket(
        market=market,
        probabilities=consensus,
        dispersion=statistics.median(absolute_deviations),
        bookmaker_count=len(fair_books),
        observed_at=max(observed),
        devig_method=method,
    )
