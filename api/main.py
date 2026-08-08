"""Small local API over Phase 1 application services."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from fpl_optimizer.database.forecast_repository import ForecastRepository
from fpl_optimizer.database.odds_repository import OddsRepository
from fpl_optimizer.database.repositories import FplRepository
from fpl_optimizer.domain.optimizer import SquadOptimizationRequest
from fpl_optimizer.domain.strategy import StrategyProfile
from fpl_optimizer.domain.team import CurrentTeamInput, CurrentTeamPlayerInput
from fpl_optimizer.scoring.presets import PRESETS
from fpl_optimizer.services.container import AppContainer

container = AppContainer.create()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    container.close()


app = FastAPI(title="FPL Optimizer", version="0.13.0", lifespan=lifespan)


class StrategyRequest(BaseModel):
    """API representation of a user-controlled decision profile."""

    name: str = "API strategy"
    mode: Literal["simple", "advanced"] = "simple"
    preset: str = "Custom"
    horizon: int = Field(default=3, ge=1, le=6)
    risk_appetite: int = Field(default=40, ge=0, le=100)
    transfer_reluctance: int = Field(default=50, ge=0, le=100)
    ownership_preference: int = Field(default=0, ge=-100, le=100)
    weights: dict[str, int]
    market_weight: float = Field(default=0.3, ge=0, le=1)

    def profile(self) -> StrategyProfile:
        """Convert the transport object to a framework-independent profile."""

        return StrategyProfile(
            name=self.name,
            mode=self.mode,
            preset=self.preset,
            horizon=self.horizon,
            risk_appetite=self.risk_appetite,
            transfer_reluctance=self.transfer_reluctance,
            ownership_preference=self.ownership_preference,
            weights=self.weights,
        )


class SquadRequest(StrategyRequest):
    """API request for an optimized initial squad."""

    budget: float = Field(default=100.0, gt=0)
    locked_player_ids: list[int] = Field(default_factory=list)
    excluded_player_ids: list[int] = Field(default_factory=list)


class CurrentTeamPlayerRequest(BaseModel):
    """One current-squad membership with team-specific prices."""

    player_id: int
    purchase_price: float = Field(gt=0)
    selling_price: float = Field(gt=0)


class CurrentTeamRequest(BaseModel):
    """Editable current-team state."""

    bank: float = Field(default=0.0, ge=0)
    free_transfers: int = Field(default=1, ge=0, le=5)
    wildcard_available: bool = True
    free_hit_available: bool = True
    bench_boost_available: bool = True
    triple_captain_available: bool = True
    players: list[CurrentTeamPlayerRequest]


class SimulationRequest(BaseModel):
    """Controls for one reproducible current-team Monte Carlo run."""

    horizon: int = Field(default=3, ge=1, le=6)
    iterations: int = Field(default=10_000, ge=1_000, le=50_000)
    seed: int = Field(default=42, ge=0)
    market_weight: float = Field(default=0.3, ge=0, le=1)


class OutcomeImportRequest(BaseModel):
    """CSV payload containing final player/Gameweek results."""

    csv_text: str = Field(min_length=1)
    source_ref: str = "API CSV import"


class TeamIdRequest(BaseModel):
    """Public FPL entry identifier."""

    team_id: int = Field(gt=0)


@app.get("/health")
def health() -> dict[str, Any]:
    """Return database availability, freshness, and core record counts."""

    with container.database.session() as session:
        repository = FplRepository(session)
        return {"status": "ok", "freshness": repository.freshness(), **repository.counts()}


@app.post("/data/fpl/refresh")
def refresh(force: bool = True) -> dict[str, Any]:
    """Refresh official FPL data and return a compact report."""

    try:
        report = container.refresh.refresh(force=force)
        return {
            "players": report.players,
            "teams": report.teams,
            "gameweeks": report.gameweeks,
            "fixtures": report.fixtures,
            "refreshed_at": report.refreshed_at,
            "used_cache": report.used_cache,
            "stale": report.stale,
            "warnings": report.warnings,
        }
    except Exception as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/players")
def players() -> list[dict[str, object]]:
    """Return current player read models."""

    with container.database.session() as session:
        return FplRepository(session).list_players()


@app.get("/fixtures")
def fixtures() -> list[dict[str, object]]:
    """Return current fixture read models."""

    with container.database.session() as session:
        return FplRepository(session).list_fixtures()


@app.post("/forecasts/statistical/run")
def run_statistical_forecasts(horizon: int = 6) -> dict[str, Any]:
    """Generate versioned basic statistical forecasts."""

    try:
        report = container.forecast.run(horizon=horizon)
        return {
            "players": report.players,
            "gameweeks": report.gameweeks,
            "forecasts": report.forecasts,
            "prediction_at": report.prediction_at,
            "input_cutoff_at": report.input_cutoff_at,
            "model_version": report.model_version,
        }
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/forecasts/statistical")
def statistical_forecasts(market_weight: float = 0.3) -> list[dict[str, object]]:
    """Return the latest 1/3/6 Gameweek player forecast summaries."""

    with container.database.session() as session:
        return ForecastRepository(session).list_player_summaries(market_weight)


@app.post("/forecasts/advanced/run")
def run_advanced_forecasts(horizon: int = 6) -> dict[str, Any]:
    """Generate Phase 9 statistical forecasts with improved minutes and extra signals."""

    return run_statistical_forecasts(horizon)


@app.get("/forecasts/advanced")
def advanced_forecasts(market_weight: float = 0.3) -> list[dict[str, object]]:
    """Return current advanced statistical and market forecast summaries."""

    return statistical_forecasts(market_weight)


@app.post("/markets/run")
def run_markets(devig_method: str = "multiplicative") -> dict[str, Any]:
    """Generate fixture and player market forecasts from stored odds."""

    try:
        report = container.markets.run(devig_method)
        return {
            "fixtures": report.fixtures,
            "player_forecasts": report.player_forecasts,
            "prediction_at": report.prediction_at,
            "devig_method": report.devig_method,
            "warnings": report.warnings,
        }
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/markets")
def markets() -> list[dict[str, object]]:
    """Return the latest market fixture forecasts."""

    with container.database.session() as session:
        return OddsRepository(session).market_dashboard()


@app.get("/strategy/presets")
def strategy_presets() -> dict[str, dict[str, object]]:
    """Return built-in strategy presets."""

    return PRESETS


@app.post("/strategy/score")
def strategy_score(request: StrategyRequest) -> list[dict[str, object]]:
    """Return dynamic player scores and their exact contribution breakdowns."""

    try:
        scores = container.strategy.score(request.profile(), request.market_weight)
        return [
            {
                "player_id": score.player_id,
                "player": score.player,
                "position": score.position,
                "team": score.team,
                "price": score.price,
                "ownership": score.ownership,
                "horizon_xpts": score.horizon_xpts,
                "value": score.value,
                "risk": score.risk,
                "optimization_score": score.score,
                "contributions": [
                    {
                        "feature": item.feature,
                        "label": item.label,
                        "raw_value": item.raw_value,
                        "percentile": item.percentile,
                        "raw_weight": item.raw_weight,
                        "normalized_weight": item.normalized_weight,
                        "contribution": item.contribution,
                    }
                    for item in score.contributions
                ],
            }
            for score in scores
        ]
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/strategies")
def save_strategy(request: StrategyRequest) -> dict[str, object]:
    """Save or replace one named local strategy."""

    try:
        return {"id": container.strategy.save(request.profile()), "name": request.name}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/strategies")
def saved_strategies() -> list[dict[str, object]]:
    """Return locally saved strategies."""

    return container.strategy.list_saved()


@app.post("/optimizer/squad")
def optimize_initial_squad(request: SquadRequest) -> dict[str, object]:
    """Generate and persist the best legal 15-player squad."""

    try:
        report = container.optimizer.run(
            request.profile(),
            request.market_weight,
            SquadOptimizationRequest(
                budget=request.budget,
                locked_player_ids=tuple(request.locked_player_ids),
                excluded_player_ids=tuple(request.excluded_player_ids),
            ),
        )
        result = report.result
        return {
            "run_id": report.run_id,
            "created_at": report.created_at,
            "status": result.status,
            "solver": result.solver,
            "budget": result.budget,
            "total_cost": result.total_cost,
            "budget_remaining": result.budget_remaining,
            "objective_score": result.objective_score,
            "total_xpts": result.total_xpts,
            "average_ownership": result.average_ownership,
            "average_risk": result.average_risk,
            "players": [
                {
                    "player_id": player.player_id,
                    "player": player.player,
                    "position": player.position,
                    "team": player.team,
                    "price": player.price,
                    "ownership": player.ownership,
                    "horizon_xpts": player.horizon_xpts,
                    "risk": player.risk,
                    "optimization_score": player.optimization_score,
                    "locked": player.locked,
                }
                for player in result.players
            ],
        }
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/optimizer/runs")
def optimization_runs() -> list[dict[str, object]]:
    """Return compact recent initial-squad runs."""

    return container.optimizer.recent()


@app.put("/team/current")
def save_current_team(request: CurrentTeamRequest) -> dict[str, object]:
    """Validate and replace the locally managed current squad."""

    try:
        team_id = container.team.save(
            CurrentTeamInput(
                name="My Team",
                bank=request.bank,
                free_transfers=request.free_transfers,
                wildcard_available=request.wildcard_available,
                free_hit_available=request.free_hit_available,
                bench_boost_available=request.bench_boost_available,
                triple_captain_available=request.triple_captain_available,
                players=tuple(
                    CurrentTeamPlayerInput(
                        player_id=player.player_id,
                        purchase_price=player.purchase_price,
                        selling_price=player.selling_price,
                    )
                    for player in request.players
                ),
            )
        )
        return {"id": team_id, "name": "My Team"}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/team/current")
def current_team() -> dict[str, object]:
    """Return the current squad and team-management state."""

    team = container.team.get()
    if team is None:
        raise HTTPException(status_code=404, detail="No current squad has been saved")
    return {
        "id": team.team_id,
        "name": team.name,
        "bank": team.bank,
        "free_transfers": team.free_transfers,
        "chips": {
            "wildcard": team.wildcard_available,
            "free_hit": team.free_hit_available,
            "bench_boost": team.bench_boost_available,
            "triple_captain": team.triple_captain_available,
        },
        "players": [
            {
                "player_id": player.player_id,
                "player": player.player,
                "position": player.position,
                "team": player.team,
                "purchase_price": player.purchase_price,
                "selling_price": player.selling_price,
                "current_price": player.current_price,
            }
            for player in team.players
        ],
    }


@app.post("/team/current/lineup")
def optimize_current_lineup(request: StrategyRequest) -> dict[str, object]:
    """Optimize and persist the current squad's next-Gameweek lineup."""

    try:
        report = container.team.optimize(request.profile(), request.market_weight)
        result = report.result
        return {
            "run_id": report.run_id,
            "created_at": report.created_at,
            "formation": result.formation,
            "captain_id": result.captain_id,
            "vice_captain_id": result.vice_captain_id,
            "base_xpts": result.base_xpts,
            "projected_points": result.projected_points,
            "next_3_squad_xpts": result.next_3_squad_xpts,
            "next_5_squad_xpts": result.next_5_squad_xpts,
            "starters": [asdict(player) for player in result.starters],
            "bench": [asdict(player) for player in result.bench],
            "captain_options": [asdict(option) for option in result.captain_options],
        }
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/team/current/lineup-runs")
def lineup_runs() -> list[dict[str, object]]:
    """Return recent current-team lineup decisions."""

    return container.team.recent_lineups()


@app.post("/transfers/evaluate")
def evaluate_current_transfers(request: StrategyRequest) -> dict[str, object]:
    """Compare rolling with the best exact one- and two-transfer plans."""

    try:
        report = container.transfers.run(request.profile(), request.market_weight)
        evaluation = report.evaluation
        return {
            "run_id": report.run_id,
            "created_at": report.created_at,
            "recommendation": evaluation.recommendation,
            "recommended_transfers": evaluation.recommended_transfers,
            "rationale": evaluation.rationale,
            "horizon": evaluation.horizon,
            "free_transfers": evaluation.free_transfers,
            "starting_bank": evaluation.starting_bank,
            "roll_flexibility_value": evaluation.roll_flexibility_value,
            "current_squad_xpts": evaluation.current_squad_xpts,
            "plans": [
                {
                    "transfers": plan.transfers,
                    "moves": [asdict(move) for move in plan.moves],
                    "final_player_ids": plan.final_player_ids,
                    "final_squad_xpts": plan.final_squad_xpts,
                    "gross_gain": plan.gross_gain,
                    "hit_cost": plan.hit_cost,
                    "net_gain": plan.net_gain,
                    "ending_bank": plan.ending_bank,
                }
                for plan in evaluation.plans
            ],
        }
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/transfers/runs")
def transfer_runs() -> list[dict[str, object]]:
    """Return recent saved transfer evaluations."""

    return container.transfers.recent()


@app.post("/planner/run")
def run_multi_gameweek_planner(request: StrategyRequest) -> dict[str, object]:
    """Jointly optimize transfers, lineups, and captains across the requested horizon."""

    try:
        report = container.planner.run(
            request.profile(), request.market_weight, request.horizon
        )
        return {
            "run_id": report.run_id,
            "created_at": report.created_at,
            "plan": asdict(report.plan),
        }
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/planner/runs")
def planner_runs() -> list[dict[str, object]]:
    """Return recent saved multi-Gameweek plans."""

    return container.planner.recent()


@app.post("/simulation/run")
def run_simulation(request: SimulationRequest) -> dict[str, object]:
    """Run and persist a reproducible current-team Monte Carlo simulation."""

    try:
        report = container.simulation.run(
            horizon=request.horizon,
            iterations=request.iterations,
            seed=request.seed,
            market_weight=request.market_weight,
        )
        return {
            "run_id": report.run_id,
            "created_at": report.created_at,
            "result": asdict(report.result),
        }
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/simulation/runs")
def simulation_runs() -> list[dict[str, object]]:
    """Return recent saved simulation runs."""

    return container.simulation.recent()


@app.post("/chips/evaluate")
def evaluate_chips(request: StrategyRequest) -> dict[str, object]:
    """Evaluate Wildcard, Free Hit, Bench Boost, and Triple Captain opportunities."""

    try:
        report = container.chips.run(
            request.profile(), request.market_weight, request.horizon
        )
        return {
            "run_id": report.run_id,
            "created_at": report.created_at,
            "evaluation": asdict(report.evaluation),
        }
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/chips/runs")
def chip_runs() -> list[dict[str, object]]:
    """Return recent saved chip evaluations."""

    return container.chips.recent()


@app.post("/backtesting/outcomes/import")
def import_backtest_outcomes(request: OutcomeImportRequest) -> dict[str, int]:
    """Validate and atomically import historical FPL outcomes."""

    try:
        return {"imported": container.backtesting.import_csv(request.csv_text, request.source_ref)}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/backtesting/outcomes/count")
def backtest_outcome_count() -> dict[str, int]:
    """Return the number of imported historical outcomes."""

    return {"outcomes": container.backtesting.outcome_count()}


@app.post("/backtesting/run")
def run_backtest() -> dict[str, object]:
    """Calibrate on historical forecasts and persist the evaluation."""

    try:
        report = container.backtesting.run()
        return {
            "run_id": report.run_id,
            "created_at": report.created_at,
            "result": asdict(report.result),
        }
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/backtesting/runs")
def backtest_runs() -> list[dict[str, object]]:
    """Return recent historical forecast evaluations."""

    return container.backtesting.recent()


@app.post("/team/import")
def import_public_team(request: TeamIdRequest, force: bool = False) -> dict[str, object]:
    """Import the latest publicly published Gameweek squad by Team ID."""

    try:
        return asdict(container.team_import.import_team(request.team_id, force=force))
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/team/imported")
def imported_public_team() -> dict[str, object] | None:
    """Return saved public team metadata and published roles."""

    summary = container.team_import.get_summary()
    return asdict(summary) if summary is not None else None


@app.get("/odds/live/status")
def live_odds_status() -> dict[str, object]:
    """Return live provider configuration and persisted freshness."""

    return asdict(container.live_odds.status())


@app.post("/odds/live/test")
def test_live_odds() -> dict[str, bool]:
    """Test the configured provider through its normal cache policy."""

    try:
        return {"connected": container.live_odds.test_connection()}
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/odds/live/refresh")
def refresh_live_odds(force: bool = False) -> dict[str, object]:
    """Fetch EPL odds, persist snapshots, and refresh market/player forecasts."""

    try:
        return asdict(container.live_odds.refresh(force=force))
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
