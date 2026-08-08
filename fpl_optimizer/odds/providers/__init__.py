"""Replaceable odds input providers."""

from fpl_optimizer.odds.providers.base import OddsProvider
from fpl_optimizer.odds.providers.csv_provider import CsvOddsProvider
from fpl_optimizer.odds.providers.manual_provider import ManualOddsProvider

__all__ = ["CsvOddsProvider", "ManualOddsProvider", "OddsProvider"]
