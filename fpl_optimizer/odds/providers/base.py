"""Odds provider protocol."""

from __future__ import annotations

from typing import Any, Protocol

from fpl_optimizer.domain.markets import GoalscorerOddsQuote, OddsQuote


class OddsProvider(Protocol):
    """Minimal interface implemented by every optional odds source."""

    @property
    def name(self) -> str: ...

    def get_quotes(self) -> list[OddsQuote | GoalscorerOddsQuote]: ...


class LiveOddsProvider(Protocol):
    """Replaceable transport interface for current league events and odds."""

    @property
    def name(self) -> str: ...

    def get_events(self, force: bool = False) -> list[dict[str, Any]]: ...

    def get_event_odds(
        self, event_ids: list[int], force: bool = False
    ) -> list[dict[str, Any]]: ...

    def test_connection(self) -> bool: ...
