"""Tests for replaceable CSV and manual odds providers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fpl_optimizer.domain.enums import OddsMarket, OddsSelection
from fpl_optimizer.domain.markets import GoalscorerOddsQuote, OddsQuote
from fpl_optimizer.odds.providers.csv_provider import CsvOddsError, CsvOddsProvider
from fpl_optimizer.odds.providers.manual_provider import ManualOddsProvider


def test_csv_provider_parses_long_form_decimal_odds() -> None:
    content = (
        "fixture_id,bookmaker,market,selection,decimal_odds,observed_at\n"
        "10,Book A,1x2,home,2.0,2026-08-08T12:00:00Z\n"
        "10,Book A,1x2,draw,3.5,2026-08-08T12:00:00Z\n"
    )

    quotes = CsvOddsProvider(content).get_quotes()

    assert len(quotes) == 2
    assert quotes[0].market is OddsMarket.MATCH_RESULT
    assert quotes[0].selection is OddsSelection.HOME
    assert quotes[0].observed_at.tzinfo is not None


def test_csv_provider_rejects_invalid_prices() -> None:
    content = (
        "fixture_id,bookmaker,market,selection,decimal_odds,observed_at\n"
        "10,Book A,1x2,home,1.0,2026-08-08T12:00:00Z\n"
    )
    with pytest.raises(CsvOddsError, match="greater than 1"):
        CsvOddsProvider(content).get_quotes()


def test_manual_provider_builds_both_complete_markets() -> None:
    provider = ManualOddsProvider(
        10,
        "Book A",
        datetime(2026, 8, 8, 12, tzinfo=UTC),
        2.0,
        3.5,
        4.0,
        1.9,
        1.95,
    )

    quotes = provider.get_quotes()

    assert len(quotes) == 5
    assert {quote.market for quote in quotes} == {
        OddsMarket.MATCH_RESULT,
        OddsMarket.TOTAL_GOALS_2_5,
    }


def test_csv_provider_parses_advanced_fixture_and_goalscorer_markets() -> None:
    content = (
        "fixture_id,bookmaker,market,selection,decimal_odds,observed_at,player_id\n"
        "10,Book A,btts,yes,1.8,2026-08-08T12:00:00Z,\n"
        "10,Book A,btts,no,2.0,2026-08-08T12:00:00Z,\n"
        "10,Book A,anytime_goalscorer,score,2.5,2026-08-08T12:00:00Z,101\n"
    )

    quotes = CsvOddsProvider(content).get_quotes()

    fixture_quote = quotes[0]
    assert isinstance(fixture_quote, OddsQuote)
    assert fixture_quote.market is OddsMarket.BTTS
    scorer = quotes[2]
    assert isinstance(scorer, GoalscorerOddsQuote)
    assert scorer.player_fpl_id == 101


def test_goalscorer_csv_requires_player_id() -> None:
    content = (
        "fixture_id,bookmaker,market,selection,decimal_odds,observed_at\n"
        "10,Book A,anytime_goalscorer,score,2.5,2026-08-08T12:00:00Z\n"
    )
    with pytest.raises(CsvOddsError, match="player_id is required"):
        CsvOddsProvider(content).get_quotes()
