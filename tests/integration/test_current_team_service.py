"""End-to-end current-team persistence and lineup optimization test."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from fpl_optimizer.database.base import Database
from fpl_optimizer.database.models import (
    DataSnapshot,
    Gameweek,
    ModelVersion,
    Player,
    PlayerForecast,
    PlayerSnapshot,
    Team,
)
from fpl_optimizer.domain.team import CurrentTeamInput, CurrentTeamPlayerInput
from fpl_optimizer.scoring.presets import preset_profile
from fpl_optimizer.services.chips import ChipService
from fpl_optimizer.services.optimizer import SquadOptimizerService
from fpl_optimizer.services.planner import MultiGameweekPlannerService
from fpl_optimizer.services.simulation import SimulationService
from fpl_optimizer.services.strategy import StrategyService
from fpl_optimizer.services.team import CurrentTeamService
from fpl_optimizer.services.transfers import TransferOptimizerService


def test_current_team_saves_and_generates_complete_lineup(tmp_path) -> None:
    database = Database(f"sqlite:///{tmp_path / 'current_team.db'}")
    database.create_schema()
    now = datetime(2026, 8, 8, 12, tzinfo=UTC)
    positions = ["GK"] * 2 + ["DEF"] * 5 + ["MID"] * 5 + ["FWD"] * 3
    with database.session() as session:
        snapshot = DataSnapshot(
            provider="test",
            endpoint="test",
            retrieved_at=now,
            payload_hash="a" * 64,
            cache_path="test.json",
            schema_version="test",
            is_valid=True,
        )
        session.add(snapshot)
        session.flush()
        teams = [
            Team(
                fpl_id=index + 1,
                name=f"Team {index}",
                short_name=f"T{index}",
                strength=3,
                strength_attack_home=1000,
                strength_attack_away=1000,
                strength_defence_home=1000,
                strength_defence_away=1000,
                snapshot_id=snapshot.id,
            )
            for index in range(5)
        ]
        session.add_all(teams)
        gameweeks = [
            Gameweek(
                fpl_id=number,
                name=f"Gameweek {number}",
                deadline_at=now + timedelta(days=5 + 7 * (number - 1)),
                is_current=False,
                is_next=number == 1,
                finished=False,
                snapshot_id=snapshot.id,
            )
            for number in range(1, 4)
        ]
        model = ModelVersion(
            name="test",
            semantic_version="1.0",
            feature_schema="test",
            parameter_json="{}",
            training_cutoff_at=None,
            code_revision="test",
            created_at=now,
        )
        session.add_all([*gameweeks, model])
        session.flush()
        for index, position in enumerate(positions):
            player = Player(
                fpl_id=100 + index,
                team_id=teams[index % 5].id,
                position=position,
                web_name=f"{position} {index}",
                first_name="Test",
                second_name=str(index),
                status="a",
                news="",
                chance_next_round=100,
                snapshot_id=snapshot.id,
            )
            session.add(player)
            session.flush()
            session.add(
                PlayerSnapshot(
                    player_id=player.id,
                    data_snapshot_id=snapshot.id,
                    observed_at=now,
                    price_tenths=45 + index,
                    total_points=index,
                    minutes=90,
                    starts=1,
                    goals=1 if position in {"MID", "FWD"} else 0,
                    assists=0,
                    clean_sheets=0,
                    saves=0,
                    bonus=0,
                    bps=0,
                    selected_pct=float(index),
                    transfers_in=0,
                    transfers_out=0,
                    form=float(index),
                    points_per_game=1.0,
                    ict_index=1.0,
                )
            )
            xpts = 2.0 + index / 10
            session.add_all(
                [
                    PlayerForecast(
                        player_id=player.id,
                        gameweek_id=gameweek.id,
                        model_version_id=model.id,
                        prediction_at=now,
                        input_cutoff_at=now,
                        expected_minutes=90,
                        appearance_xpts=2,
                        goal_xpts=xpts - 2,
                        assist_xpts=0,
                        clean_sheet_xpts=0,
                        save_xpts=0,
                        bonus_xpts=0,
                        deduction_xpts=0,
                        stat_xpts=xpts,
                        fixture_count=1,
                        opponent_summary="TST (H)",
                        confidence="High",
                        component_json=json.dumps({"fixtures": []}),
                    )
                    for gameweek in gameweeks
                ]
            )

    strategy_service = StrategyService(database)
    squad_optimizer = SquadOptimizerService(database, strategy_service)
    service = CurrentTeamService(database, strategy_service, squad_optimizer)
    choices = service.player_choices()
    input_team = CurrentTeamInput(
        name="My Team",
        bank=1.5,
        free_transfers=2,
        wildcard_available=True,
        free_hit_available=False,
        bench_boost_available=True,
        triple_captain_available=True,
        players=tuple(
            CurrentTeamPlayerInput(
                player_id=int(row["Player ID"]),
                purchase_price=float(row["Price"]),
                selling_price=float(row["Price"]),
            )
            for row in choices
        ),
    )

    team_id = service.save(input_team)
    saved = service.get()
    report = service.optimize(preset_profile("Balanced", "simple"), 0.3)
    transfer_service = TransferOptimizerService(database, strategy_service)
    transfer_report = transfer_service.run(preset_profile("Balanced", "simple"), 0.3)
    planner_service = MultiGameweekPlannerService(database, strategy_service)
    planner_report = planner_service.run(preset_profile("Balanced", "simple"), 0.3, 3)
    simulation_service = SimulationService(database)
    simulation_report = simulation_service.run(
        horizon=3, iterations=1_000, seed=42, market_weight=0.3
    )
    chip_service = ChipService(database, strategy_service)
    chip_report = chip_service.run(preset_profile("Balanced", "simple"), 0.3, 3)

    assert team_id > 0
    assert saved is not None
    assert saved.bank == 1.5
    assert saved.free_transfers == 2
    assert len(saved.players) == 15
    assert len(report.result.starters) == 11
    assert len(report.result.bench) == 4
    assert report.result.captain_id != report.result.vice_captain_id
    assert service.recent_lineups()[0]["Run ID"] == report.run_id
    assert transfer_report.evaluation.recommendation == "ROLL TRANSFER"
    assert [plan.transfers for plan in transfer_report.evaluation.plans] == [0]
    assert transfer_service.recent()[0]["Run ID"] == transfer_report.run_id
    assert len(planner_report.plan.weeks) == 3
    assert planner_report.plan.total_transfers == 0
    assert planner_service.recent()[0]["Run ID"] == planner_report.run_id
    assert simulation_report.result.iterations == 1_000
    assert len(simulation_report.result.weeks) == 3
    assert simulation_service.recent()[0]["Run ID"] == simulation_report.run_id
    assert len(chip_report.evaluation.opportunities) == 4
    assert chip_service.recent()[0]["Run ID"] == chip_report.run_id
    database.engine.dispose()
