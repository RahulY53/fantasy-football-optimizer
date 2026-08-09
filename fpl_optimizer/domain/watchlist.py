"""Framework-independent player watchlist records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class WatchlistEntry:
    """One persistent player watchlist membership."""

    player_id: int
    full_name: str
    team: str
    position: str
    note: str
    created_at: datetime
    updated_at: datetime
