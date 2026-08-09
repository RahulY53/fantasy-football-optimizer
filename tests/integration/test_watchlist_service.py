"""Integration tests for persistent player watchlist membership."""

from __future__ import annotations

import httpx
import pytest

from fpl_optimizer.data.cache import JsonCache
from fpl_optimizer.data.fpl.client import FplClient
from fpl_optimizer.database.base import Database
from fpl_optimizer.database.repositories import FplRepository
from fpl_optimizer.services.refresh import RefreshService
from fpl_optimizer.services.watchlist import WatchlistService


def test_watchlist_persists_membership_notes_and_idempotent_changes(
    tmp_path, bootstrap_payload, fixture_payload
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/bootstrap-static/"):
            return httpx.Response(200, json=bootstrap_payload)
        if request.url.path.endswith("/fixtures/"):
            return httpx.Response(200, json=fixture_payload)
        return httpx.Response(404)

    database = Database(f"sqlite:///{tmp_path / 'watchlist.db'}")
    database.create_schema()
    client = FplClient(
        "https://example.test/api",
        JsonCache(tmp_path / "cache"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    RefreshService(database, client).refresh(force=True)
    with database.session() as session:
        players = FplRepository(session).list_players()
    first_id = int(players[0]["Player ID"])
    second_id = int(players[1]["Player ID"])
    service = WatchlistService(database)

    assert service.add_many([first_id, second_id, first_id], "Monitor fixtures") == 2
    assert service.add_many([first_id]) == 0
    assert service.ids() == frozenset({first_id, second_id})
    entries = service.entries()
    assert {entry.full_name for entry in entries} == {
        str(players[0]["Full Name"]),
        str(players[1]["Full Name"]),
    }
    assert all(entry.note == "Monitor fixtures" for entry in entries)

    assert service.update_note(first_id, "  Potential transfer  ")
    assert not service.update_note(first_id, "Potential transfer")
    assert next(entry for entry in service.entries() if entry.player_id == first_id).note == (
        "Potential transfer"
    )
    assert service.remove_many([second_id, second_id]) == 1
    assert service.ids() == frozenset({first_id})

    with pytest.raises(ValueError, match="Unknown player"):
        service.add_many([999999])

    client.close()
    database.engine.dispose()
