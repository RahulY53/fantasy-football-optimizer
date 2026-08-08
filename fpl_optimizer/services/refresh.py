"""Official FPL refresh orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from fpl_optimizer.data.fpl.client import FetchResult, FplClient
from fpl_optimizer.data.fpl.mapper import map_bootstrap, map_fixtures
from fpl_optimizer.database.base import Database
from fpl_optimizer.database.repositories import FplRepository, SnapshotInput

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RefreshReport:
    """A user-facing summary of a completed atomic refresh."""

    players: int
    teams: int
    gameweeks: int
    fixtures: int
    refreshed_at: datetime
    used_cache: bool
    stale: bool
    warnings: tuple[str, ...]


class RefreshService:
    """Fetch, validate, and transactionally persist official FPL data."""

    def __init__(self, database: Database, client: FplClient) -> None:
        self.database = database
        self.client = client

    def refresh(self, force: bool = False) -> RefreshReport:
        """Refresh bootstrap and fixtures without partially updating the database."""

        bootstrap_result = self.client.bootstrap(force=force)
        fixture_result = self.client.fixtures(force=force)
        bootstrap = map_bootstrap(bootstrap_result.payload)
        fixtures = map_fixtures(fixture_result.payload)

        with self.database.session() as session:
            repository = FplRepository(session)
            bootstrap_snapshot = repository.record_snapshot(_snapshot_input(bootstrap_result))
            fixture_snapshot = repository.record_snapshot(_snapshot_input(fixture_result))
            repository.upsert_bootstrap(bootstrap, bootstrap_snapshot)
            repository.upsert_fixtures(fixtures, fixture_snapshot)

        warnings = tuple(
            result.warning
            for result in (bootstrap_result, fixture_result)
            if result.warning is not None
        )
        report = RefreshReport(
            players=len(bootstrap.players),
            teams=len(bootstrap.teams),
            gameweeks=len(bootstrap.gameweeks),
            fixtures=len(fixtures),
            refreshed_at=max(
                bootstrap_result.entry.retrieved_at, fixture_result.entry.retrieved_at
            ),
            used_cache=bootstrap_result.from_cache or fixture_result.from_cache,
            stale=bootstrap_result.stale or fixture_result.stale,
            warnings=warnings,
        )
        LOGGER.info("FPL refresh complete report=%s", report)
        return report


def _snapshot_input(result: FetchResult) -> SnapshotInput:
    return SnapshotInput(
        endpoint=result.endpoint,
        retrieved_at=result.entry.retrieved_at,
        payload_hash=result.entry.payload_hash,
        cache_path=result.entry.payload_path,
    )
