"""Persistence for a current FPL squad and lineup decisions."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from fpl_optimizer.database.models import (
    LineupRun,
    Player,
    PlayerSnapshot,
    Team,
    UserPlayer,
    UserTeam,
)
from fpl_optimizer.domain.names import resolved_player_name
from fpl_optimizer.domain.strategy import StrategyProfile
from fpl_optimizer.domain.team import (
    CurrentTeam,
    CurrentTeamInput,
    CurrentTeamPlayer,
    CurrentTeamPlayerInput,
    LineupResult,
    PublishedTeamImport,
    PublishedTeamSummary,
)


def _usable_team_price(stored_tenths: int, current_tenths: int) -> float:
    """Fall back to the official current price for legacy zero-price imports."""

    return (stored_tenths if stored_tenths > 0 else current_tenths) / 10


class CurrentTeamRepository:
    """Create, replace, and read one named local current team."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, value: CurrentTeamInput) -> UserTeam:
        """Upsert team metadata and atomically replace all 15 memberships."""

        now = datetime.now(UTC)
        row = self.session.scalar(select(UserTeam).where(UserTeam.name == value.name))
        if row is None:
            row = UserTeam(
                name=value.name,
                bank_tenths=round(value.bank * 10),
                free_transfers=value.free_transfers,
                wildcard_available=value.wildcard_available,
                free_hit_available=value.free_hit_available,
                bench_boost_available=value.bench_boost_available,
                triple_captain_available=value.triple_captain_available,
                created_at=now,
                updated_at=now,
            )
            self.session.add(row)
            self.session.flush()
        row.bank_tenths = round(value.bank * 10)
        row.free_transfers = value.free_transfers
        row.wildcard_available = value.wildcard_available
        row.free_hit_available = value.free_hit_available
        row.bench_boost_available = value.bench_boost_available
        row.triple_captain_available = value.triple_captain_available
        row.updated_at = now
        row.fpl_team_id = None
        row.manager_name = None
        row.imported_team_name = None
        row.overall_rank = None
        row.total_points = None
        row.published_gameweek = None
        row.squad_value_tenths = None
        row.data_status = None
        row.imported_at = None
        row.history_json = None
        row.transfers_json = None
        self.session.execute(delete(UserPlayer).where(UserPlayer.user_team_id == row.id))
        self.session.add_all(
            UserPlayer(
                user_team_id=row.id,
                player_id=player.player_id,
                purchase_price_tenths=round(player.purchase_price * 10),
                selling_price_tenths=round(player.selling_price * 10),
            )
            for player in value.players
        )
        return row

    def get(self, name: str = "My Team") -> CurrentTeam | None:
        """Return a saved team with current canonical player metadata."""

        row = self.session.scalar(select(UserTeam).where(UserTeam.name == name))
        if row is None:
            return None
        latest = (
            select(
                PlayerSnapshot.player_id,
                func.max(PlayerSnapshot.observed_at).label("observed_at"),
            )
            .group_by(PlayerSnapshot.player_id)
            .subquery()
        )
        statement = (
            select(UserPlayer, Player, Team, PlayerSnapshot)
            .join(Player, UserPlayer.player_id == Player.id)
            .join(Team, Player.team_id == Team.id)
            .join(PlayerSnapshot, PlayerSnapshot.player_id == Player.id)
            .join(
                latest,
                (latest.c.player_id == PlayerSnapshot.player_id)
                & (latest.c.observed_at == PlayerSnapshot.observed_at),
            )
            .where(UserPlayer.user_team_id == row.id)
            .order_by(Player.position, Player.display_name)
        )
        players = tuple(
            CurrentTeamPlayer(
                player_id=player.id,
                player=resolved_player_name(
                    player.display_name,
                    player.first_name,
                    player.second_name,
                    player.web_name,
                ),
                position=player.position,
                team=team.short_name,
                purchase_price=_usable_team_price(
                    membership.purchase_price_tenths, snapshot.price_tenths
                ),
                selling_price=_usable_team_price(
                    membership.selling_price_tenths, snapshot.price_tenths
                ),
                current_price=snapshot.price_tenths / 10,
            )
            for membership, player, team, snapshot in self.session.execute(statement)
        )
        if len(players) != 15:
            return None
        return CurrentTeam(
            team_id=row.id,
            name=row.name,
            bank=row.bank_tenths / 10,
            free_transfers=row.free_transfers,
            wildcard_available=row.wildcard_available,
            free_hit_available=row.free_hit_available,
            bench_boost_available=row.bench_boost_available,
            triple_captain_available=row.triple_captain_available,
            players=players,
        )

    def save_published_import(self, value: PublishedTeamImport) -> UserTeam:
        """Replace My Team with an official-ID-mapped published Gameweek squad."""

        current = CurrentTeamInput(
            name="My Team",
            bank=value.bank,
            free_transfers=1,
            wildcard_available=True,
            free_hit_available=True,
            bench_boost_available=True,
            triple_captain_available=True,
            players=tuple(
                CurrentTeamPlayerInput(
                    player_id=player.player_id,
                    purchase_price=player.purchase_price,
                    selling_price=player.selling_price,
                )
                for player in value.players
            ),
        )
        row = self.save(current)
        row.fpl_team_id = value.fpl_team_id
        row.manager_name = value.manager_name
        row.imported_team_name = value.team_name
        row.overall_rank = value.overall_rank
        row.total_points = value.total_points
        row.published_gameweek = value.published_gameweek
        row.squad_value_tenths = (
            round(value.squad_value * 10) if value.squad_value is not None else None
        )
        row.data_status = value.data_status
        row.imported_at = value.refreshed_at
        row.history_json = json.dumps(value.history, sort_keys=True)
        row.transfers_json = json.dumps(value.transfers, sort_keys=True)
        roles = {player.player_id: player for player in value.players}
        memberships = self.session.scalars(
            select(UserPlayer).where(UserPlayer.user_team_id == row.id)
        )
        for membership in memberships:
            role = roles[membership.player_id]
            membership.imported_position = role.pick_position
            membership.is_starting = role.is_starting
            membership.bench_order = role.bench_order
            membership.is_captain = role.is_captain
            membership.is_vice_captain = role.is_vice_captain
        self.session.flush()
        return row

    def save_pending_import(self, value: PublishedTeamImport) -> UserTeam:
        """Remember a valid pre-GW1 entry without inventing a public squad."""

        now = datetime.now(UTC)
        row = self.session.scalar(select(UserTeam).where(UserTeam.name == "My Team"))
        if row is None:
            row = UserTeam(
                name="My Team",
                bank_tenths=0,
                free_transfers=1,
                wildcard_available=True,
                free_hit_available=True,
                bench_boost_available=True,
                triple_captain_available=True,
                created_at=now,
                updated_at=now,
            )
            self.session.add(row)
        row.fpl_team_id = value.fpl_team_id
        row.manager_name = value.manager_name
        row.imported_team_name = value.team_name
        row.overall_rank = value.overall_rank
        row.total_points = value.total_points
        row.published_gameweek = None
        row.squad_value_tenths = None
        row.data_status = value.data_status
        row.imported_at = value.refreshed_at
        row.history_json = "[]"
        row.transfers_json = "[]"
        row.updated_at = now
        self.session.flush()
        return row

    def published_summary(self) -> PublishedTeamSummary | None:
        """Return persisted public-import metadata and published selection roles."""

        row = self.session.scalar(select(UserTeam).where(UserTeam.name == "My Team"))
        if row is None or row.fpl_team_id is None or row.imported_at is None:
            return None
        memberships = list(
            self.session.scalars(
                select(UserPlayer)
                .where(UserPlayer.user_team_id == row.id)
                .order_by(UserPlayer.imported_position)
            )
        )
        captain = next((item.player_id for item in memberships if item.is_captain), 0)
        vice = next((item.player_id for item in memberships if item.is_vice_captain), 0)
        history = json.loads(row.history_json or "[]")
        transfers = json.loads(row.transfers_json or "[]")
        transfer_player_ids = {
            int(item[key])
            for item in transfers
            for key in ("element_in", "element_out")
            if item.get(key) is not None
        }
        player_names = {
            player.fpl_id: resolved_player_name(
                player.display_name,
                player.first_name,
                player.second_name,
                player.web_name,
            )
            for player in self.session.scalars(
                select(Player).where(Player.fpl_id.in_(transfer_player_ids))
            )
        }
        return PublishedTeamSummary(
            fpl_team_id=row.fpl_team_id,
            manager_name=row.manager_name or "Unknown manager",
            team_name=row.imported_team_name or "Unnamed team",
            overall_rank=row.overall_rank,
            total_points=row.total_points or 0,
            published_gameweek=row.published_gameweek or 0,
            squad_value=(
                row.squad_value_tenths / 10 if row.squad_value_tenths is not None else None
            ),
            bank=row.bank_tenths / 10,
            refreshed_at=row.imported_at,
            data_status=row.data_status or "Published GW Squad",
            starting_ids=tuple(item.player_id for item in memberships if item.is_starting),
            bench_ids=tuple(item.player_id for item in memberships if not item.is_starting),
            captain_id=captain,
            vice_captain_id=vice,
            transfer_count=len(transfers),
            recent_history=tuple(history[-10:]),
            recent_transfers=tuple(
                {
                    "Gameweek": item.get("event"),
                    "Transferred out": player_names.get(
                        int(item.get("element_out") or 0),
                        f"Player #{item.get('element_out')}",
                    ),
                    "Sale price": (
                        float(item["element_out_cost"]) / 10
                        if item.get("element_out_cost") is not None
                        else None
                    ),
                    "Transferred in": player_names.get(
                        int(item.get("element_in") or 0),
                        f"Player #{item.get('element_in')}",
                    ),
                    "Buy price": (
                        float(item["element_in_cost"]) / 10
                        if item.get("element_in_cost") is not None
                        else None
                    ),
                    "Time": item.get("time"),
                }
                for item in transfers[-10:]
            ),
        )

    def save_lineup(
        self,
        *,
        team_id: int,
        result: LineupResult,
        profile: StrategyProfile,
        market_weight: float,
        forecast_at: datetime,
        created_at: datetime,
    ) -> LineupRun:
        """Persist one reproducible lineup recommendation."""

        row = LineupRun(
            user_team_id=team_id,
            created_at=created_at,
            forecast_at=forecast_at,
            market_weight=market_weight,
            formation=result.formation,
            projected_points=result.projected_points,
            strategy_json=json.dumps(asdict(profile), sort_keys=True),
            result_json=json.dumps(asdict(result), sort_keys=True),
        )
        self.session.add(row)
        self.session.flush()
        return row

    def recent_lineups(self, limit: int = 10) -> list[dict[str, object]]:
        """Return compact recent lineup-run summaries."""

        rows = self.session.scalars(
            select(LineupRun).order_by(LineupRun.created_at.desc()).limit(limit)
        )
        return [
            {
                "Run ID": row.id,
                "Created": row.created_at,
                "Forecasted": row.forecast_at,
                "Formation": row.formation,
                "Projected points": row.projected_points,
                "Market weight": row.market_weight,
            }
            for row in rows
        ]
