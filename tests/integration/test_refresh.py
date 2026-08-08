"""End-to-end Phase 1 refresh using recorded provider responses."""

from __future__ import annotations

import httpx

from fpl_optimizer.data.cache import JsonCache
from fpl_optimizer.data.fpl.client import FplClient
from fpl_optimizer.database.base import Database
from fpl_optimizer.database.repositories import FplRepository
from fpl_optimizer.services.refresh import RefreshService


def test_refresh_is_atomic_and_idempotent(tmp_path, bootstrap_payload, fixture_payload) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/bootstrap-static/"):
            return httpx.Response(200, json=bootstrap_payload)
        if request.url.path.endswith("/fixtures/"):
            return httpx.Response(200, json=fixture_payload)
        return httpx.Response(404)

    database = Database(f"sqlite:///{tmp_path / 'test.db'}")
    database.create_schema()
    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = FplClient(
        "https://example.test/api",
        JsonCache(tmp_path / "cache"),
        http_client=http,
    )
    service = RefreshService(database, client)

    first = service.refresh(force=True)
    second = service.refresh(force=False)

    assert first.players == 4
    assert first.fixtures == 2
    assert second.used_cache
    with database.session() as session:
        repository = FplRepository(session)
        assert repository.counts() == {
            "players": 4,
            "teams": 2,
            "fixtures": 2,
            "gameweeks": 2,
        }
        players = repository.list_players()
        fixtures = repository.list_fixtures()
        assert players[0]["Player"] == "Sam Playmaker"
        assert players[0]["Full Name"] == "Sam Playmaker"
        assert "playmaker" in players[0]["Name Search"]
        assert fixtures[0]["Home"] == "North London"
    database.engine.dispose()
