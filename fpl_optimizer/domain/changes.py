"""Framework-independent player change-detection records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ChangeWindow:
    """The two observations compared for one source."""

    source: str
    previous_at: datetime | None
    current_at: datetime | None

    @property
    def comparable(self) -> bool:
        """Return whether the source has two distinct observations."""

        return self.previous_at is not None and self.current_at is not None


@dataclass(frozen=True, slots=True)
class PlayerChange:
    """Material differences for one player across the latest source observations."""

    player_id: int
    full_name: str
    team: str
    position: str
    watchlisted: bool
    price: float | None
    price_delta: float | None
    ownership: float | None
    ownership_delta: float | None
    expected_minutes: float | None
    expected_minutes_delta: float | None
    blended_xpts: float | None
    blended_xpts_delta: float | None
    xpts_3gw: float | None
    xpts_3gw_delta: float | None
    xpts_5gw: float | None
    xpts_5gw_delta: float | None
    market_xpts: float | None
    market_xpts_delta: float | None
    goal_probability: float | None
    goal_probability_delta: float | None
    status_before: str | None
    status: str | None
    news_before: str | None
    news: str | None
    chance_next_round: int | None
    change_types: tuple[str, ...]
    significance: float


@dataclass(frozen=True, slots=True)
class ChangeReport:
    """Latest cross-source player changes and their comparison windows."""

    changes: tuple[PlayerChange, ...]
    windows: tuple[ChangeWindow, ...]

    @property
    def has_baseline(self) -> bool:
        """Return whether at least one source can be compared."""

        return any(window.comparable for window in self.windows)

