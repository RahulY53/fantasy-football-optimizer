"""Persistence tests for cached Model Lab diagnostics."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fpl_optimizer.database.base import Database
from fpl_optimizer.database.model_lab_repository import ModelLabRepository
from fpl_optimizer.database.models import (
    DataSnapshot,
    Gameweek,
    ModelVersion,
    Player,
    PlayerForecast,
    PlayerMarketForecast,
    Team,
)


def test_model_lab_reblends_cached_rows_and_filters_sensitive_parameters(tmp_path) -> None:
    database = Database(f"sqlite:///{tmp_path / 'model-lab.db'}")
    database.create_schema()
    now = datetime(2026, 8, 9, 12, tzinfo=UTC)
    with database.session() as session:
        snapshot = DataSnapshot(
            provider="test",
            endpoint="test",
            retrieved_at=now,
            payload_hash="a" * 64,
            cache_path="cache.json",
            schema_version="test",
            is_valid=True,
        )
        session.add(snapshot)
        session.flush()
        team = Team(
            fpl_id=1,
            name="Test Team",
            short_name="TST",
            strength=3,
            strength_attack_home=1000,
            strength_attack_away=1000,
            strength_defence_home=1000,
            strength_defence_away=1000,
            snapshot_id=snapshot.id,
        )
        gameweek = Gameweek(
            fpl_id=1,
            name="Gameweek 1",
            deadline_at=now,
            is_current=False,
            is_next=True,
            finished=False,
            snapshot_id=snapshot.id,
        )
        model = ModelVersion(
            name="test-model",
            semantic_version="1.0.0",
            feature_schema="test-v1",
            parameter_json=json.dumps(
                {"horizon": 6, "api_key": "must-not-render", "service_url": "private"}
            ),
            training_cutoff_at=None,
            code_revision="abc123",
            created_at=now,
        )
        session.add_all([team, gameweek, model])
        session.flush()
        player = Player(
            fpl_id=10,
            team_id=team.id,
            position="MID",
            web_name="Tester",
            first_name="Model",
            second_name="Tester",
            full_name="Model Tester",
            display_name="Model Tester",
            status="a",
            news="",
            chance_next_round=100,
            snapshot_id=snapshot.id,
        )
        session.add(player)
        session.flush()
        session.add(
            PlayerForecast(
                player_id=player.id,
                gameweek_id=gameweek.id,
                model_version_id=model.id,
                prediction_at=now,
                input_cutoff_at=now,
                expected_minutes=80.0,
                appearance_xpts=2.0,
                goal_xpts=2.0,
                assist_xpts=1.0,
                clean_sheet_xpts=0.5,
                save_xpts=0.0,
                bonus_xpts=0.5,
                deduction_xpts=0.0,
                defensive_contribution_xpts=0.0,
                stat_xpts=6.0,
                fixture_count=1,
                opponent_summary="OPP (H)",
                confidence="High",
                component_json=json.dumps({"p_start": 0.8}),
            )
        )
        session.add(
            PlayerMarketForecast(
                player_id=player.id,
                gameweek_id=gameweek.id,
                prediction_at=now,
                input_cutoff_at=now,
                appearance_xpts=2.0,
                goal_xpts=3.0,
                assist_xpts=1.0,
                clean_sheet_xpts=0.5,
                save_xpts=0.0,
                bonus_xpts=1.0,
                deduction_xpts=0.0,
                defensive_contribution_xpts=0.0,
                market_xpts=8.0,
                fixture_count=1,
                confidence="Medium",
                component_json="{}",
                goalscorer_probability=0.4,
            )
        )

    with database.session() as session:
        repository = ModelLabRepository(session)
        statistical = repository.diagnostics(0.0)
        market = repository.diagnostics(1.0)
        versions = repository.versions()

    assert statistical[0].blended_xpts == 6.0
    assert market[0].blended_xpts == 8.0
    assert market[0].market_edge == 2.0
    assert market[0].start_probability == 0.8
    assert versions[0].parameters == (("horizon", "6"),)
