"""Transactional persistence and read models for Phase 1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from fpl_optimizer.database.models import (
    DataSnapshot,
    Fixture,
    Gameweek,
    Player,
    PlayerSnapshot,
    Team,
)
from fpl_optimizer.domain.records import BootstrapData, FixtureRecord


@dataclass(frozen=True, slots=True)
class SnapshotInput:
    """Raw cache metadata to persist with canonical records."""

    endpoint: str
    retrieved_at: datetime
    payload_hash: str
    cache_path: Path


class FplRepository:
    """Persist mapped FPL data and provide UI-ready read models."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def record_snapshot(self, value: SnapshotInput) -> DataSnapshot:
        """Return an existing immutable snapshot or create it."""

        existing = self.session.scalar(
            select(DataSnapshot).where(
                DataSnapshot.endpoint == value.endpoint,
                DataSnapshot.payload_hash == value.payload_hash,
                DataSnapshot.retrieved_at == value.retrieved_at,
            )
        )
        if existing is not None:
            return existing
        row = DataSnapshot(
            provider="official-fpl",
            endpoint=value.endpoint,
            retrieved_at=value.retrieved_at,
            payload_hash=value.payload_hash,
            cache_path=str(value.cache_path),
            schema_version="fpl-v1",
            is_valid=True,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def upsert_bootstrap(self, data: BootstrapData, snapshot: DataSnapshot) -> None:
        """Upsert bootstrap identities and append one metric snapshot per payload."""

        for gameweek_item in data.gameweeks:
            gameweek_row = self._gameweek(gameweek_item.fpl_id) or Gameweek(
                fpl_id=gameweek_item.fpl_id
            )
            gameweek_row.name = gameweek_item.name
            gameweek_row.deadline_at = gameweek_item.deadline_at
            gameweek_row.is_current = gameweek_item.is_current
            gameweek_row.is_next = gameweek_item.is_next
            gameweek_row.finished = gameweek_item.finished
            gameweek_row.snapshot_id = snapshot.id
            self.session.add(gameweek_row)

        for team_item in data.teams:
            team_row = self._team(team_item.fpl_id) or Team(fpl_id=team_item.fpl_id)
            team_row.name = team_item.name
            team_row.short_name = team_item.short_name
            team_row.strength = team_item.strength
            team_row.strength_attack_home = team_item.strength_attack_home
            team_row.strength_attack_away = team_item.strength_attack_away
            team_row.strength_defence_home = team_item.strength_defence_home
            team_row.strength_defence_away = team_item.strength_defence_away
            team_row.snapshot_id = snapshot.id
            self.session.add(team_row)
        self.session.flush()

        team_ids: dict[int, int] = {
            fpl_id: database_id
            for fpl_id, database_id in self.session.execute(select(Team.fpl_id, Team.id))
        }
        for player_item in data.players:
            player_row = self._player(player_item.fpl_id) or Player(fpl_id=player_item.fpl_id)
            player_row.team_id = team_ids[player_item.team_fpl_id]
            player_row.position = player_item.position.value
            player_row.web_name = player_item.web_name
            player_row.first_name = player_item.first_name
            player_row.second_name = player_item.second_name
            player_row.status = player_item.status
            player_row.news = player_item.news
            player_row.chance_next_round = player_item.chance_next_round
            player_row.snapshot_id = snapshot.id
            self.session.add(player_row)
            self.session.flush()

            existing_snapshot = self.session.scalar(
                select(PlayerSnapshot).where(
                    PlayerSnapshot.player_id == player_row.id,
                    PlayerSnapshot.data_snapshot_id == snapshot.id,
                )
            )
            if existing_snapshot is None:
                self.session.add(
                    PlayerSnapshot(
                        player_id=player_row.id,
                        data_snapshot_id=snapshot.id,
                        observed_at=snapshot.retrieved_at,
                        price_tenths=player_item.price_tenths,
                        total_points=player_item.total_points,
                        minutes=player_item.minutes,
                        starts=player_item.starts,
                        goals=player_item.goals,
                        assists=player_item.assists,
                        clean_sheets=player_item.clean_sheets,
                        saves=player_item.saves,
                        bonus=player_item.bonus,
                        bps=player_item.bps,
                        selected_pct=player_item.selected_pct,
                        transfers_in=player_item.transfers_in,
                        transfers_out=player_item.transfers_out,
                        form=player_item.form,
                        points_per_game=player_item.points_per_game,
                        ict_index=player_item.ict_index,
                        own_goals=player_item.own_goals,
                        penalties_saved=player_item.penalties_saved,
                        penalties_missed=player_item.penalties_missed,
                        yellow_cards=player_item.yellow_cards,
                        red_cards=player_item.red_cards,
                        clearances_blocks_interceptions=(
                            player_item.clearances_blocks_interceptions
                        ),
                        tackles=player_item.tackles,
                        recoveries=player_item.recoveries,
                        defensive_contribution=player_item.defensive_contribution,
                    )
                )

    def upsert_fixtures(self, fixtures: tuple[FixtureRecord, ...], snapshot: DataSnapshot) -> None:
        """Upsert fixtures after bootstrap teams and gameweeks exist."""

        team_ids: dict[int, int] = {
            fpl_id: database_id
            for fpl_id, database_id in self.session.execute(select(Team.fpl_id, Team.id))
        }
        gameweek_ids: dict[int, int] = {
            fpl_id: database_id
            for fpl_id, database_id in self.session.execute(select(Gameweek.fpl_id, Gameweek.id))
        }
        for fixture_item in fixtures:
            fixture_row = self._fixture(fixture_item.fpl_id) or Fixture(fpl_id=fixture_item.fpl_id)
            fixture_row.gameweek_id = (
                gameweek_ids.get(fixture_item.gameweek_fpl_id)
                if fixture_item.gameweek_fpl_id is not None
                else None
            )
            fixture_row.home_team_id = team_ids[fixture_item.home_team_fpl_id]
            fixture_row.away_team_id = team_ids[fixture_item.away_team_fpl_id]
            fixture_row.kickoff_at = fixture_item.kickoff_at
            fixture_row.home_difficulty = fixture_item.home_difficulty
            fixture_row.away_difficulty = fixture_item.away_difficulty
            fixture_row.status = fixture_item.status.value
            fixture_row.home_score = fixture_item.home_score
            fixture_row.away_score = fixture_item.away_score
            fixture_row.snapshot_id = snapshot.id
            self.session.add(fixture_row)

    def list_players(self) -> list[dict[str, object]]:
        """Return the latest current player table for presentation."""

        latest = (
            select(
                PlayerSnapshot.player_id,
                func.max(PlayerSnapshot.observed_at).label("observed_at"),
            )
            .group_by(PlayerSnapshot.player_id)
            .subquery()
        )
        statement = (
            select(Player, Team, PlayerSnapshot)
            .join(Team, Player.team_id == Team.id)
            .join(PlayerSnapshot, PlayerSnapshot.player_id == Player.id)
            .join(
                latest,
                (latest.c.player_id == PlayerSnapshot.player_id)
                & (latest.c.observed_at == PlayerSnapshot.observed_at),
            )
            .order_by(PlayerSnapshot.total_points.desc(), Player.web_name)
        )
        rows = self.session.execute(statement).all()
        return [
            {
                "Player": player.web_name,
                "Player ID": player.id,
                "Position": player.position,
                "Team": team.short_name,
                "Price": metrics.price_tenths / 10,
                "Points": metrics.total_points,
                "Minutes": metrics.minutes,
                "Starts": metrics.starts,
                "Goals": metrics.goals,
                "Assists": metrics.assists,
                "Clean sheets": metrics.clean_sheets,
                "Ownership %": metrics.selected_pct,
                "Form": metrics.form,
                "Points/game": metrics.points_per_game,
                "BPS": metrics.bps,
                "ICT index": metrics.ict_index,
                "Defensive contributions": metrics.defensive_contribution,
                "CBI": metrics.clearances_blocks_interceptions,
                "Tackles": metrics.tackles,
                "Recoveries": metrics.recoveries,
                "Transfers in": metrics.transfers_in,
                "Transfers out": metrics.transfers_out,
                "Status": player.status,
                "News": player.news,
                "Updated": metrics.observed_at,
            }
            for player, team, metrics in rows
        ]

    def list_fixtures(self) -> list[dict[str, object]]:
        """Return fixtures with display team and gameweek names."""

        home = aliased(Team)
        away = aliased(Team)
        statement = (
            select(Fixture, Gameweek, home, away)
            .join(home, Fixture.home_team_id == home.id)
            .join(away, Fixture.away_team_id == away.id)
            .outerjoin(Gameweek, Fixture.gameweek_id == Gameweek.id)
            .order_by(Fixture.kickoff_at.is_(None), Fixture.kickoff_at, Fixture.fpl_id)
        )
        return [
            {
                "Gameweek": gameweek.name if gameweek else "Unscheduled",
                "Kickoff": fixture.kickoff_at,
                "Home": home_team.name,
                "Away": away_team.name,
                "Home difficulty": fixture.home_difficulty,
                "Away difficulty": fixture.away_difficulty,
                "Status": fixture.status,
                "Score": (
                    f"{fixture.home_score}–{fixture.away_score}"
                    if fixture.home_score is not None and fixture.away_score is not None
                    else ""
                ),
            }
            for fixture, gameweek, home_team, away_team in self.session.execute(statement)
        ]

    def freshness(self) -> datetime | None:
        """Return the latest successful source retrieval timestamp."""

        return self.session.scalar(select(func.max(DataSnapshot.retrieved_at)))

    def counts(self) -> dict[str, int]:
        """Return key record counts for health and empty-state checks."""

        return {
            "players": self.session.scalar(select(func.count(Player.id))) or 0,
            "teams": self.session.scalar(select(func.count(Team.id))) or 0,
            "fixtures": self.session.scalar(select(func.count(Fixture.id))) or 0,
            "gameweeks": self.session.scalar(select(func.count(Gameweek.id))) or 0,
        }

    def _gameweek(self, fpl_id: int) -> Gameweek | None:
        return self.session.scalar(select(Gameweek).where(Gameweek.fpl_id == fpl_id))

    def _team(self, fpl_id: int) -> Team | None:
        return self.session.scalar(select(Team).where(Team.fpl_id == fpl_id))

    def _player(self, fpl_id: int) -> Player | None:
        return self.session.scalar(select(Player).where(Player.fpl_id == fpl_id))

    def _fixture(self, fpl_id: int) -> Fixture | None:
        return self.session.scalar(select(Fixture).where(Fixture.fpl_id == fpl_id))
