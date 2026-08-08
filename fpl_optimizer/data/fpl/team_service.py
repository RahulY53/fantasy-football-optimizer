"""Public FPL Team ID client and strict response mapper."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fpl_optimizer.data.fpl.client import FplClient


class PublicTeamUnavailableError(RuntimeError):
    """Raised when a public team cannot be safely imported."""


class NoPublishedGameweekError(ValueError):
    """Raised when a valid entry exists before its first public picks release."""


class PublicFplTeamService:
    """Fetch entry, published picks, history, and transfers through the shared client."""

    def __init__(self, client: FplClient) -> None:
        self.client = client

    def fetch(self, team_id: int, *, force: bool = False) -> dict[str, Any]:
        """Return validated public team payloads for the latest published Gameweek."""

        if team_id <= 0:
            raise ValueError("FPL Team ID must be a positive number")
        try:
            entry = self.client.fetch(f"/entry/{team_id}/", force=force).payload
        except (RuntimeError, ValueError) as error:
            raise PublicTeamUnavailableError(
                f"FPL Team ID {team_id} was not found, or the public FPL service is unavailable."
            ) from error
        if not isinstance(entry, dict) or int(entry.get("id") or 0) != team_id:
            raise PublicTeamUnavailableError("FPL returned malformed entry details")
        try:
            bootstrap = self.client.bootstrap(force=force).payload
            gameweek = latest_published_gameweek(bootstrap, entry)
        except NoPublishedGameweekError:
            return {
                "entry": entry,
                "gameweek": 0,
                "picks": [],
                "history": [],
                "transfers": [],
                "retrieved_at": datetime.now(UTC),
            }
        except (RuntimeError, ValueError) as error:
            raise PublicTeamUnavailableError(
                "The team is valid, but current FPL Gameweek data could not be loaded."
            ) from error
        try:
            picks = self.client.fetch(
                f"/entry/{team_id}/event/{gameweek}/picks/", force=force
            ).payload
        except (RuntimeError, ValueError) as error:
            raise PublicTeamUnavailableError(
                f"The team is valid, but its published Gameweek {gameweek} picks are unavailable."
            ) from error
        if not isinstance(picks, dict):
            raise PublicTeamUnavailableError("FPL returned malformed published picks")
        pick_rows = picks.get("picks")
        if not isinstance(pick_rows, list) or len(pick_rows) != 15:
            raise PublicTeamUnavailableError(
                f"Gameweek {gameweek} does not expose a complete published 15-player squad"
            )
        history = _optional_fetch(self.client, f"/entry/{team_id}/history/", force)
        transfers = _optional_fetch(self.client, f"/entry/{team_id}/transfers/", force)
        current_history = history.get("current", []) if isinstance(history, dict) else []
        if not isinstance(current_history, list):
            current_history = []
        if not isinstance(transfers, list):
            transfers = []
        return {
            "entry": entry,
            "gameweek": gameweek,
            "picks": pick_rows,
            "history": current_history,
            "transfers": transfers,
            "retrieved_at": datetime.now(UTC),
        }


def latest_published_gameweek(bootstrap: object, entry: object) -> int:
    """Determine the newest public picks Gameweek without hard-coding season state."""

    if not isinstance(bootstrap, dict) or not isinstance(entry, dict):
        raise ValueError("Malformed FPL Gameweek data")
    events = bootstrap.get("events")
    if not isinstance(events, list):
        raise ValueError("FPL Gameweek data is unavailable")
    available = [
        int(event["id"])
        for event in events
        if isinstance(event, dict) and event.get("finished") and event.get("id") is not None
    ]
    current_event = entry.get("current_event")
    if isinstance(current_event, int) and current_event > 0:
        available.append(current_event)
    if not available:
        raise NoPublishedGameweekError("The season has not published a Gameweek squad yet")
    return max(available)


def _optional_fetch(client: FplClient, endpoint: str, force: bool) -> object:
    try:
        return client.fetch(endpoint, force=force).payload
    except (RuntimeError, ValueError):
        return []
