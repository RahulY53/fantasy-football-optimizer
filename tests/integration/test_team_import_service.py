"""Persistence coverage for official player mapping and published squad roles."""

from __future__ import annotations

from datetime import UTC, datetime

from fpl_optimizer.database.base import Database
from fpl_optimizer.database.models import DataSnapshot, Player, Team
from fpl_optimizer.services.team_import import TeamImportService


class _PublicService:
    def fetch(self, team_id: int, *, force: bool = False):
        return {
            "entry": {
                "player_first_name": "Ada",
                "player_last_name": "Lovelace",
                "name": "Expected Engines",
                "summary_overall_rank": 1234,
                "summary_overall_points": 100,
                "last_deadline_value": 1015,
                "last_deadline_bank": 12,
            },
            "gameweek": 3,
            "picks": [
                {
                    "element": 100 + position,
                    "position": position,
                    "purchase_price": 50,
                    "selling_price": 51,
                    "is_captain": position == 1,
                    "is_vice_captain": position == 2,
                }
                for position in range(1, 16)
            ],
            "history": [{"event": 3}],
            "transfers": [{"event": 3}],
            "retrieved_at": datetime(2026, 8, 8, tzinfo=UTC),
        }


class _PreseasonPublicService:
    def fetch(self, team_id: int, *, force: bool = False):
        return {
            "entry": {
                "id": team_id,
                "player_first_name": "Rahul",
                "player_last_name": "Yelisetti",
                "name": "2Slow2Placid",
                "summary_overall_rank": None,
                "summary_overall_points": None,
                "last_deadline_value": None,
                "last_deadline_bank": None,
            },
            "gameweek": 0,
            "picks": [],
            "history": [],
            "transfers": [],
            "retrieved_at": datetime(2026, 8, 8, tzinfo=UTC),
        }


def test_team_import_maps_official_ids_and_persists_roles(tmp_path) -> None:
    database = Database(f"sqlite:///{tmp_path / 'team-import.db'}")
    database.create_schema()
    with database.session() as session:
        snapshot = DataSnapshot(
            provider="test",
            endpoint="test",
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
            payload_hash="a" * 64,
            cache_path="test",
            schema_version="test",
            is_valid=True,
        )
        session.add(snapshot)
        session.flush()
        team = Team(
            fpl_id=1,
            name="Arsenal",
            short_name="ARS",
            strength=3,
            strength_attack_home=3,
            strength_attack_away=3,
            strength_defence_home=3,
            strength_defence_away=3,
            snapshot_id=snapshot.id,
        )
        session.add(team)
        session.flush()
        session.add_all(
            Player(
                fpl_id=100 + position,
                team_id=team.id,
                position="MID",
                web_name=f"P{position}",
                first_name="Test",
                second_name=str(position),
                status="a",
                news="",
                chance_next_round=None,
                snapshot_id=snapshot.id,
            )
            for position in range(1, 16)
        )

    service = TeamImportService(database, _PublicService())  # type: ignore[arg-type]
    summary = service.import_team(42)

    assert summary.fpl_team_id == 42
    assert summary.manager_name == "Ada Lovelace"
    assert len(summary.starting_ids) == 11
    assert len(summary.bench_ids) == 4
    assert summary.captain_id == summary.starting_ids[0]
    assert summary.vice_captain_id == summary.starting_ids[1]
    assert summary.bank == 1.2
    database.engine.dispose()


def test_preseason_import_persists_valid_team_id_without_a_fake_squad(tmp_path) -> None:
    database = Database(f"sqlite:///{tmp_path / 'preseason-team.db'}")
    database.create_schema()
    service = TeamImportService(database, _PreseasonPublicService())  # type: ignore[arg-type]

    summary = service.import_team(3322414)

    assert summary.fpl_team_id == 3322414
    assert summary.manager_name == "Rahul Yelisetti"
    assert summary.team_name == "2Slow2Placid"
    assert summary.published_gameweek == 0
    assert summary.starting_ids == ()
    assert summary.data_status == "Awaiting first published squad"
    database.engine.dispose()
