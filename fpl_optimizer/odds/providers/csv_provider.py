"""Validated CSV odds import provider."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from fpl_optimizer.domain.enums import OddsMarket, OddsSelection, OddsSnapshotKind
from fpl_optimizer.domain.markets import GoalscorerOddsQuote, OddsQuote

REQUIRED_COLUMNS = {
    "fixture_id",
    "bookmaker",
    "market",
    "selection",
    "decimal_odds",
    "observed_at",
}
MARKET_ALIASES = {
    "1x2": OddsMarket.MATCH_RESULT,
    "match_result": OddsMarket.MATCH_RESULT,
    "over_under_2_5": OddsMarket.TOTAL_GOALS_2_5,
    "ou2.5": OddsMarket.TOTAL_GOALS_2_5,
    "btts": OddsMarket.BTTS,
    "both_teams_to_score": OddsMarket.BTTS,
    "home_total_1_5": OddsMarket.HOME_TOTAL_1_5,
    "away_total_1_5": OddsMarket.AWAY_TOTAL_1_5,
    "anytime_goalscorer": OddsMarket.ANYTIME_GOALSCORER,
}
SELECTION_ALIASES = {
    "home": OddsSelection.HOME,
    "h": OddsSelection.HOME,
    "draw": OddsSelection.DRAW,
    "d": OddsSelection.DRAW,
    "away": OddsSelection.AWAY,
    "a": OddsSelection.AWAY,
    "over": OddsSelection.OVER,
    "o": OddsSelection.OVER,
    "under": OddsSelection.UNDER,
    "u": OddsSelection.UNDER,
    "yes": OddsSelection.YES,
    "y": OddsSelection.YES,
    "no": OddsSelection.NO,
    "n": OddsSelection.NO,
    "score": OddsSelection.SCORE,
}


class CsvOddsError(ValueError):
    """Raised when an odds CSV cannot be safely imported."""


class CsvOddsProvider:
    """Parse the documented long-form decimal-odds CSV format."""

    name = "csv"

    def __init__(self, content: str | bytes, source_ref: str = "uploaded.csv") -> None:
        self.content = content.decode("utf-8-sig") if isinstance(content, bytes) else content
        self.source_ref = source_ref

    def get_quotes(self) -> list[OddsQuote | GoalscorerOddsQuote]:
        """Parse and validate every row; partial imports are never returned."""

        reader = csv.DictReader(io.StringIO(self.content))
        if reader.fieldnames is None or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
            missing = sorted(REQUIRED_COLUMNS - set(reader.fieldnames or []))
            raise CsvOddsError(f"Missing required columns: {', '.join(missing)}")

        quotes: list[OddsQuote | GoalscorerOddsQuote] = []
        for row_number, row in enumerate(reader, start=2):
            try:
                market = MARKET_ALIASES[row["market"].strip().lower()]
                selection = SELECTION_ALIASES[row["selection"].strip().lower()]
                _validate_selection(market, selection)
                decimal_odds = float(row["decimal_odds"])
                if decimal_odds <= 1.0:
                    raise ValueError("decimal_odds must be greater than 1")
                observed_at = _parse_datetime(row["observed_at"])
                kind_text = (row.get("snapshot_kind") or "current").strip().lower()
                if market is OddsMarket.ANYTIME_GOALSCORER:
                    player_id = int(row.get("player_id") or 0)
                    if player_id <= 0:
                        raise ValueError(
                            "player_id is required for anytime_goalscorer rows"
                        )
                    quotes.append(
                        GoalscorerOddsQuote(
                            fixture_fpl_id=int(row["fixture_id"]),
                            player_fpl_id=player_id,
                            provider="csv",
                            bookmaker=row["bookmaker"].strip(),
                            decimal_odds=decimal_odds,
                            observed_at=observed_at,
                            snapshot_kind=OddsSnapshotKind(kind_text),
                            source_ref=self.source_ref,
                        )
                    )
                else:
                    quotes.append(
                        OddsQuote(
                            fixture_fpl_id=int(row["fixture_id"]),
                            provider="csv",
                            bookmaker=row["bookmaker"].strip(),
                            market=market,
                            selection=selection,
                            decimal_odds=decimal_odds,
                            observed_at=observed_at,
                            snapshot_kind=OddsSnapshotKind(kind_text),
                            source_ref=self.source_ref,
                        )
                    )
                if not quotes[-1].bookmaker:
                    raise ValueError("bookmaker cannot be blank")
            except (KeyError, TypeError, ValueError) as error:
                raise CsvOddsError(f"Invalid odds CSV row {row_number}: {error}") from error
        if not quotes:
            raise CsvOddsError("Odds CSV contains no data rows")
        return quotes


def _validate_selection(market: OddsMarket, selection: OddsSelection) -> None:
    allowed = {
        OddsMarket.MATCH_RESULT: {
            OddsSelection.HOME,
            OddsSelection.DRAW,
            OddsSelection.AWAY,
        },
        OddsMarket.TOTAL_GOALS_2_5: {OddsSelection.OVER, OddsSelection.UNDER},
        OddsMarket.BTTS: {OddsSelection.YES, OddsSelection.NO},
        OddsMarket.HOME_TOTAL_1_5: {OddsSelection.OVER, OddsSelection.UNDER},
        OddsMarket.AWAY_TOTAL_1_5: {OddsSelection.OVER, OddsSelection.UNDER},
        OddsMarket.ANYTIME_GOALSCORER: {OddsSelection.SCORE},
    }
    if selection not in allowed[market]:
        raise ValueError(f"selection {selection.value} is invalid for market {market.value}")


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
