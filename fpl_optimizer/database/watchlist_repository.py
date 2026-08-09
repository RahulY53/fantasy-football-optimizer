"""Persistence operations for the canonical player watchlist."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpl_optimizer.database.models import Player, PlayerWatchlist, Team
from fpl_optimizer.domain.names import resolved_player_name
from fpl_optimizer.domain.watchlist import WatchlistEntry


class WatchlistRepository:
    """Read and mutate persistent watchlist membership in one transaction."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self) -> tuple[WatchlistEntry, ...]:
        """Return watchlist entries in newest-first order."""

        statement = (
            select(PlayerWatchlist, Player, Team.short_name)
            .join(Player, PlayerWatchlist.player_id == Player.id)
            .join(Team, Player.team_id == Team.id)
            .order_by(PlayerWatchlist.created_at.desc(), Player.id)
        )
        return tuple(
            WatchlistEntry(
                player_id=player.id,
                full_name=resolved_player_name(
                    player.full_name,
                    player.first_name,
                    player.second_name,
                    player.web_name,
                ),
                team=team,
                position=player.position,
                note=entry.note,
                created_at=entry.created_at,
                updated_at=entry.updated_at,
            )
            for entry, player, team in self.session.execute(statement)
        )

    def ids(self) -> frozenset[int]:
        """Return canonical player IDs currently on the watchlist."""

        return frozenset(self.session.scalars(select(PlayerWatchlist.player_id)))

    def add(self, player_id: int, note: str = "") -> bool:
        """Add a player if absent and return whether membership changed."""

        if self.session.get(Player, player_id) is None:
            raise ValueError(f"Unknown player ID: {player_id}")
        existing = self.session.scalar(
            select(PlayerWatchlist).where(PlayerWatchlist.player_id == player_id)
        )
        if existing is not None:
            return False
        now = datetime.now(UTC)
        self.session.add(
            PlayerWatchlist(
                player_id=player_id,
                note=note.strip(),
                created_at=now,
                updated_at=now,
            )
        )
        return True

    def remove(self, player_id: int) -> bool:
        """Remove a player if present and return whether membership changed."""

        existing = self.session.scalar(
            select(PlayerWatchlist).where(PlayerWatchlist.player_id == player_id)
        )
        if existing is None:
            return False
        self.session.delete(existing)
        return True

    def update_note(self, player_id: int, note: str) -> bool:
        """Update a watchlist note and return whether its value changed."""

        existing = self.session.scalar(
            select(PlayerWatchlist).where(PlayerWatchlist.player_id == player_id)
        )
        if existing is None:
            raise ValueError(f"Player ID {player_id} is not on the watchlist")
        cleaned = note.strip()
        if existing.note == cleaned:
            return False
        existing.note = cleaned
        existing.updated_at = datetime.now(UTC)
        return True
