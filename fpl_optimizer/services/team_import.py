"""Map and persist a public FPL Team ID squad."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from fpl_optimizer.data.fpl.team_service import PublicFplTeamService
from fpl_optimizer.database.base import Database
from fpl_optimizer.database.models import Player, PlayerSnapshot
from fpl_optimizer.database.team_repository import CurrentTeamRepository
from fpl_optimizer.domain.team import (
    PublishedSquadPlayer,
    PublishedTeamImport,
    PublishedTeamSummary,
)


class TeamImportService:
    """Import public FPL squads using official element IDs only."""

    def __init__(self, database: Database, public_service: PublicFplTeamService) -> None:
        self.database = database
        self.public_service = public_service

    def import_team(self, team_id: int, *, force: bool = False) -> PublishedTeamSummary:
        """Fetch, map, validate, and save a published 15-player squad."""

        payload = self.public_service.fetch(team_id, force=force)
        pick_rows = payload["picks"]
        if not pick_rows:
            imported = _build_import(payload, team_id, ())
            with self.database.session() as session:
                CurrentTeamRepository(session).save_pending_import(imported)
            summary = self.get_summary()
            if summary is None:
                raise RuntimeError("Registered FPL team could not be saved")
            return summary
        element_ids = [int(row["element"]) for row in pick_rows]
        with self.database.session() as session:
            players = {
                row.fpl_id: row.id
                for row in session.scalars(select(Player).where(Player.fpl_id.in_(element_ids)))
            }
            latest = (
                select(
                    PlayerSnapshot.player_id,
                    func.max(PlayerSnapshot.observed_at).label("observed_at"),
                )
                .group_by(PlayerSnapshot.player_id)
                .subquery()
            )
            current_prices = {
                fpl_id: price_tenths / 10
                for fpl_id, price_tenths in session.execute(
                    select(Player.fpl_id, PlayerSnapshot.price_tenths)
                    .join(PlayerSnapshot, PlayerSnapshot.player_id == Player.id)
                    .join(
                        latest,
                        (latest.c.player_id == PlayerSnapshot.player_id)
                        & (latest.c.observed_at == PlayerSnapshot.observed_at),
                    )
                    .where(Player.fpl_id.in_(element_ids))
                )
            }
        missing = sorted(set(element_ids) - players.keys())
        if missing:
            raise ValueError(
                "Refresh official FPL data before importing; missing player IDs: "
                + ", ".join(map(str, missing))
            )
        imported = _build_import(
            payload,
            team_id,
            tuple(_map_pick(row, players, current_prices) for row in pick_rows),
        )
        with self.database.session() as session:
            CurrentTeamRepository(session).save_published_import(imported)
        summary = self.get_summary()
        if summary is None:
            raise RuntimeError("Imported team could not be read back")
        return summary

    def get_summary(self) -> PublishedTeamSummary | None:
        """Return saved public-import metadata and published roles."""

        with self.database.session() as session:
            return CurrentTeamRepository(session).published_summary()


def _map_pick(
    row: dict[str, Any],
    players: dict[int, int],
    current_prices: dict[int, float],
) -> PublishedSquadPlayer:
    fpl_id = int(row["element"])
    current_price = current_prices.get(fpl_id)
    position = int(row.get("position") or 0)
    return PublishedSquadPlayer(
        player_id=players[fpl_id],
        purchase_price=_pick_price(row, "purchase_price", "selling_price", current_price, fpl_id),
        selling_price=_pick_price(row, "selling_price", "purchase_price", current_price, fpl_id),
        pick_position=position,
        is_starting=position <= 11,
        bench_order=position - 11 if position > 11 else None,
        is_captain=bool(row.get("is_captain")),
        is_vice_captain=bool(row.get("is_vice_captain")),
    )


def _pick_price(
    row: dict[str, Any],
    preferred: str,
    alternate: str,
    current_price: float | None,
    fpl_id: int,
) -> float:
    """Resolve an FPL tenths price without persisting an unusable zero."""

    for field in (preferred, alternate):
        raw = row.get(field)
        if raw is not None and float(raw) > 0:
            return float(raw) / 10
    if current_price is not None and current_price > 0:
        return current_price
    raise ValueError(
        f"FPL did not provide a usable price for player {fpl_id}; refresh official data "
        "and import the team again"
    )


def _build_import(
    payload: dict[str, Any],
    team_id: int,
    players: tuple[PublishedSquadPlayer, ...],
) -> PublishedTeamImport:
    entry = payload["entry"]
    gameweek = int(payload["gameweek"])
    return PublishedTeamImport(
        fpl_team_id=team_id,
        manager_name=_manager_name(entry),
        team_name=str(entry.get("name") or "Unnamed team"),
        overall_rank=_optional_int(entry.get("summary_overall_rank")),
        total_points=int(entry.get("summary_overall_points") or 0),
        published_gameweek=gameweek,
        squad_value=_tenths(entry.get("last_deadline_value")),
        bank=_tenths(entry.get("last_deadline_bank")) or 0.0,
        refreshed_at=payload["retrieved_at"],
        data_status=("Published GW Squad" if gameweek else "Awaiting first published squad"),
        players=players,
        history=tuple(payload["history"]),
        transfers=tuple(payload["transfers"]),
    )


def _optional_int(value: object) -> int | None:
    return int(str(value)) if value is not None else None


def _tenths(value: object) -> float | None:
    return float(str(value)) / 10 if value is not None else None


def _manager_name(entry: dict[str, Any]) -> str:
    parts = (
        str(entry.get("player_first_name", "")).strip(),
        str(entry.get("player_last_name", "")).strip(),
    )
    return " ".join(part for part in parts if part) or "Unknown manager"
