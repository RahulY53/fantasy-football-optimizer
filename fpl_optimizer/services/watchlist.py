"""Application service for persistent player watchlist membership."""

from __future__ import annotations

from fpl_optimizer.database.base import Database
from fpl_optimizer.database.watchlist_repository import WatchlistRepository
from fpl_optimizer.domain.watchlist import WatchlistEntry


class WatchlistService:
    """Expose transactional watchlist operations to UI adapters."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def entries(self) -> tuple[WatchlistEntry, ...]:
        """Return all persistent watchlist entries."""

        with self.database.session() as session:
            return WatchlistRepository(session).list()

    def ids(self) -> frozenset[int]:
        """Return all watched canonical player IDs."""

        with self.database.session() as session:
            return WatchlistRepository(session).ids()

    def add_many(self, player_ids: list[int] | tuple[int, ...], note: str = "") -> int:
        """Add multiple players idempotently and return the number added."""

        with self.database.session() as session:
            repository = WatchlistRepository(session)
            return sum(repository.add(player_id, note) for player_id in dict.fromkeys(player_ids))

    def remove_many(self, player_ids: list[int] | tuple[int, ...]) -> int:
        """Remove multiple players idempotently and return the number removed."""

        with self.database.session() as session:
            repository = WatchlistRepository(session)
            return sum(repository.remove(player_id) for player_id in dict.fromkeys(player_ids))

    def update_note(self, player_id: int, note: str) -> bool:
        """Update one player's persistent watchlist note."""

        with self.database.session() as session:
            return WatchlistRepository(session).update_note(player_id, note)
