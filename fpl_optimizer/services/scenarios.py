"""Session-only scenario orchestration over cached forecasts and exact solvers."""

from __future__ import annotations

from dataclasses import replace

from fpl_optimizer.database.base import Database
from fpl_optimizer.database.forecast_repository import ForecastRepository
from fpl_optimizer.database.strategy_repository import StrategyRepository
from fpl_optimizer.database.team_repository import CurrentTeamRepository
from fpl_optimizer.domain.chips import ChipCandidate, ChipOpportunity
from fpl_optimizer.domain.scenarios import (
    ScenarioAssumptions,
    ScenarioPlayerChoice,
    ScenarioPlayerImpact,
    WhatIfContext,
    WhatIfReport,
)
from fpl_optimizer.domain.strategy import PlayerStrategyInput, PlayerStrategyScore, StrategyProfile
from fpl_optimizer.domain.team import CurrentTeam
from fpl_optimizer.domain.transfers import TransferCandidate, TransferEvaluation
from fpl_optimizer.optimizer.chips import evaluate_forced_chip
from fpl_optimizer.optimizer.transfers import evaluate_transfers
from fpl_optimizer.scoring.optimization_score import score_players


class WhatIfService:
    """Compare untouched baseline decisions with temporary scenario assumptions."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def context(self, profile: StrategyProfile, market_weight: float) -> WhatIfContext:
        """Return selectable players, teams, Gameweeks, and available chips."""

        with self.database.session() as session:
            inputs = StrategyRepository(session).player_inputs(market_weight, profile.horizon)
            team = CurrentTeamRepository(session).get()
            gameweeks, _ = ForecastRepository(session).planning_matrix(
                profile.horizon, market_weight
            )
        current_ids = {player.player_id for player in team.players} if team else set()
        chips = _available_chips(team) if team else ()
        return WhatIfContext(
            players=tuple(
                ScenarioPlayerChoice(
                    player_id=item.player_id,
                    player=item.player,
                    team=item.team,
                    position=item.position,
                    is_current=item.player_id in current_ids,
                )
                for item in sorted(inputs, key=lambda row: (row.player, row.team))
            ),
            teams=tuple(sorted({item.team for item in inputs})),
            gameweeks=tuple(gameweeks),
            available_chips=chips,
        )

    def run(
        self,
        profile: StrategyProfile,
        market_weight: float,
        assumptions: ScenarioAssumptions,
    ) -> WhatIfReport:
        """Run baseline and adjusted decisions without writing forecasts or results."""

        with self.database.session() as session:
            inputs = StrategyRepository(session).player_inputs(market_weight, profile.horizon)
            team = CurrentTeamRepository(session).get()
            gameweeks, _ = ForecastRepository(session).planning_matrix(
                profile.horizon, market_weight
            )
        if team is None:
            raise RuntimeError("Save a current squad before running what-if analysis")
        if not inputs or not gameweeks:
            raise RuntimeError("Generate forecasts before running what-if analysis")
        _validate_assumptions(assumptions, inputs, team, gameweeks)
        adjusted_inputs = apply_assumptions(inputs, assumptions)
        baseline_scores = score_players(inputs, profile)
        scenario_scores = score_players(adjusted_inputs, profile)
        if adjusted_inputs == inputs and not _has_transfer_rules(assumptions):
            baseline_transfers = _evaluate_transfer_scenario(
                inputs, baseline_scores, team, profile, ScenarioAssumptions()
            )
            scenario_transfers = baseline_transfers
        else:
            baseline_transfers = _evaluate_transfer_scenario(
                inputs,
                baseline_scores,
                team,
                profile,
                ScenarioAssumptions(),
            )
            scenario_transfers = _evaluate_transfer_scenario(
                adjusted_inputs,
                scenario_scores,
                team,
                profile,
                assumptions,
            )
        baseline_chip: ChipOpportunity | None = None
        scenario_chip: ChipOpportunity | None = None
        if assumptions.forced_chip is not None:
            baseline_chip = _evaluate_chip_scenario(
                inputs, baseline_scores, team, gameweeks, assumptions
            )
            scenario_chip = _evaluate_chip_scenario(
                adjusted_inputs, scenario_scores, team, gameweeks, assumptions
            )
        return WhatIfReport(
            assumptions=_assumption_labels(assumptions, inputs, gameweeks),
            baseline_transfers=baseline_transfers,
            scenario_transfers=scenario_transfers,
            baseline_chip=baseline_chip,
            scenario_chip=scenario_chip,
            impacts=_player_impacts(inputs, adjusted_inputs),
        )


def apply_assumptions(
    inputs: list[PlayerStrategyInput], assumptions: ScenarioAssumptions
) -> list[PlayerStrategyInput]:
    """Return adjusted copies of cached strategy inputs."""

    unavailable = set(assumptions.unavailable_player_ids)
    output: list[PlayerStrategyInput] = []
    for player in inputs:
        if player.player_id in unavailable:
            output.append(
                replace(
                    player,
                    status="u",
                    chance_next_round=0,
                    horizon_xpts=0.0,
                    week_xpts=tuple(0.0 for _ in player.week_xpts),
                    expected_minutes=0.0,
                    attacking_xpts=0.0,
                    clean_sheet_xpts=0.0,
                    bonus_xpts=0.0,
                    defensive_contribution_xpts=0.0,
                )
            )
            continue
        minutes_factor = 1.0
        expected_minutes = player.expected_minutes
        if (
            player.player_id == assumptions.start_player_id
            and assumptions.start_probability is not None
        ):
            probability = assumptions.start_probability / 100.0
            expected_minutes = probability * 90.0 + (1.0 - probability) * 20.0
            minutes_factor = expected_minutes / max(player.expected_minutes, 1.0)
        attack_factor = (
            1.0 + assumptions.attack_change / 100.0
            if assumptions.attack_team == player.team
            else 1.0
        )
        attacking = player.attacking_xpts * minutes_factor * attack_factor
        non_attacking = max(player.horizon_xpts - player.attacking_xpts, 0.0)
        horizon = non_attacking * minutes_factor + attacking
        horizon_factor = horizon / player.horizon_xpts if player.horizon_xpts > 0 else 1.0
        output.append(
            replace(
                player,
                horizon_xpts=horizon,
                week_xpts=tuple(value * horizon_factor for value in player.week_xpts),
                expected_minutes=expected_minutes,
                attacking_xpts=attacking,
                clean_sheet_xpts=player.clean_sheet_xpts * minutes_factor,
                bonus_xpts=player.bonus_xpts * minutes_factor,
                defensive_contribution_xpts=(
                    player.defensive_contribution_xpts * minutes_factor
                ),
            )
        )
    return output


def _evaluate_transfer_scenario(
    inputs: list[PlayerStrategyInput],
    scores: list[PlayerStrategyScore],
    team: CurrentTeam,
    profile: StrategyProfile,
    assumptions: ScenarioAssumptions,
) -> TransferEvaluation:
    input_by_id = {item.player_id: item for item in inputs}
    current = {player.player_id: player for player in team.players}
    candidates = [
        TransferCandidate(
            player_id=score.player_id,
            player=score.player,
            position=score.position,
            team=score.team,
            buy_price=score.price,
            selling_price=(
                current[score.player_id].selling_price if score.player_id in current else None
            ),
            horizon_xpts=input_by_id[score.player_id].horizon_xpts,
            optimization_score=score.score,
            is_current=score.player_id in current,
        )
        for score in scores
    ]
    unavailable = set(assumptions.unavailable_player_ids) - set(current)
    constrained = (
        set(assumptions.protected_player_ids)
        | set(assumptions.must_sell_player_ids)
        | set(assumptions.must_buy_player_ids)
        | set(assumptions.excluded_player_ids)
        | unavailable
    )
    candidates = prune_dominated_transfer_candidates(candidates, constrained)
    return evaluate_transfers(
        candidates,
        bank=team.bank,
        free_transfers=team.free_transfers,
        transfer_reluctance=profile.transfer_reluctance,
        horizon=profile.horizon,
        protected_player_ids=set(assumptions.protected_player_ids),
        must_sell_player_ids=set(assumptions.must_sell_player_ids),
        must_buy_player_ids=set(assumptions.must_buy_player_ids),
        excluded_player_ids=set(assumptions.excluded_player_ids) | unavailable,
    )


def prune_dominated_transfer_candidates(
    candidates: list[TransferCandidate], constrained_ids: set[int]
) -> list[TransferCandidate]:
    """Remove only same-club/position targets dominated on price and both objectives."""

    retained: list[TransferCandidate] = []
    targets = [candidate for candidate in candidates if not candidate.is_current]
    for candidate in candidates:
        if candidate.is_current or candidate.player_id in constrained_ids:
            retained.append(candidate)
            continue
        dominated = any(
            other.player_id != candidate.player_id
            and other.position == candidate.position
            and other.team == candidate.team
            and other.buy_price <= candidate.buy_price
            and other.horizon_xpts >= candidate.horizon_xpts
            and other.optimization_score >= candidate.optimization_score
            and (
                other.buy_price < candidate.buy_price
                or other.horizon_xpts > candidate.horizon_xpts
                or other.optimization_score > candidate.optimization_score
            )
            for other in targets
        )
        if not dominated:
            retained.append(candidate)
    return retained


def _evaluate_chip_scenario(
    inputs: list[PlayerStrategyInput],
    scores: list[PlayerStrategyScore],
    team: CurrentTeam,
    gameweeks: list[tuple[int, str]],
    assumptions: ScenarioAssumptions,
) -> ChipOpportunity:
    score_by_id = {score.player_id: score for score in scores}
    current = {player.player_id: player for player in team.players}
    candidates = [
        ChipCandidate(
            player_id=item.player_id,
            player=item.player,
            position=item.position,
            team=item.team,
            price=(
                current[item.player_id].selling_price
                if item.player_id in current
                else item.price
            ),
            optimization_score=score_by_id[item.player_id].score,
            gameweek_xpts=item.week_xpts,
        )
        for item in inputs
    ]
    budget = team.bank + sum(player.selling_price for player in team.players)
    if assumptions.forced_chip is None or assumptions.forced_gameweek_id is None:
        raise ValueError("A forced chip scenario requires a chip and Gameweek")
    return evaluate_forced_chip(
        candidates,
        current_ids=set(current),
        budget=budget,
        gameweeks=gameweeks,
        chip=assumptions.forced_chip,
        gameweek_id=assumptions.forced_gameweek_id,
        available=assumptions.forced_chip in _available_chips(team),
    )


_CHIPS = ("Wildcard", "Free Hit", "Bench Boost", "Triple Captain")


def _available_chips(team: CurrentTeam) -> tuple[str, ...]:
    return tuple(
        chip
        for chip, available in zip(
            _CHIPS,
            (
                team.wildcard_available,
                team.free_hit_available,
                team.bench_boost_available,
                team.triple_captain_available,
            ),
            strict=True,
        )
        if available
    )


def _has_transfer_rules(assumptions: ScenarioAssumptions) -> bool:
    return any(
        (
            assumptions.protected_player_ids,
            assumptions.must_sell_player_ids,
            assumptions.must_buy_player_ids,
            assumptions.excluded_player_ids,
        )
    )


def _validate_assumptions(
    assumptions: ScenarioAssumptions,
    inputs: list[PlayerStrategyInput],
    team: CurrentTeam,
    gameweeks: list[tuple[int, str]],
) -> None:
    ids = {item.player_id for item in inputs}
    referenced = (
        set(assumptions.unavailable_player_ids)
        | set(assumptions.protected_player_ids)
        | set(assumptions.must_sell_player_ids)
        | set(assumptions.must_buy_player_ids)
        | set(assumptions.excluded_player_ids)
    )
    if assumptions.start_player_id is not None:
        referenced.add(assumptions.start_player_id)
    if referenced - ids:
        raise ValueError("Scenario contains a player without a current forecast")
    if assumptions.start_probability is not None and not 0 <= assumptions.start_probability <= 100:
        raise ValueError("Start probability must be between zero and 100")
    if (assumptions.start_player_id is None) != (assumptions.start_probability is None):
        raise ValueError("A start assumption requires both a player and a probability")
    if not -50 <= assumptions.attack_change <= 50:
        raise ValueError("Team attack change must be between -50% and +50%")
    if assumptions.attack_team is not None and assumptions.attack_team not in {
        item.team for item in inputs
    }:
        raise ValueError("Scenario attack team is unknown")
    current_ids = {player.player_id for player in team.players}
    if set(assumptions.protected_player_ids) - current_ids:
        raise ValueError("Only current players can be protected from sale")
    if assumptions.forced_chip is not None:
        if assumptions.forced_chip not in _CHIPS:
            raise ValueError("Scenario chip is unsupported")
        if assumptions.forced_gameweek_id not in {gameweek[0] for gameweek in gameweeks}:
            raise ValueError("Scenario chip Gameweek is outside the selected horizon")


def _player_impacts(
    baseline: list[PlayerStrategyInput], scenario: list[PlayerStrategyInput]
) -> tuple[ScenarioPlayerImpact, ...]:
    adjusted = {item.player_id: item for item in scenario}
    rows = [
        ScenarioPlayerImpact(
            player_id=item.player_id,
            player=item.player,
            team=item.team,
            baseline_xpts=item.horizon_xpts,
            scenario_xpts=adjusted[item.player_id].horizon_xpts,
            change=adjusted[item.player_id].horizon_xpts - item.horizon_xpts,
        )
        for item in baseline
        if abs(adjusted[item.player_id].horizon_xpts - item.horizon_xpts) > 1e-8
    ]
    return tuple(sorted(rows, key=lambda row: (-abs(row.change), row.player)))


def _assumption_labels(
    assumptions: ScenarioAssumptions,
    inputs: list[PlayerStrategyInput],
    gameweeks: list[tuple[int, str]],
) -> tuple[str, ...]:
    names = {item.player_id: item.player for item in inputs}
    labels: list[str] = []
    if assumptions.start_player_id is not None and assumptions.start_probability is not None:
        labels.append(
            f"{names[assumptions.start_player_id]} start probability: "
            f"{assumptions.start_probability:.0f}%"
        )
    if assumptions.unavailable_player_ids:
        labels.append(
            "Unavailable: "
            + ", ".join(names[player_id] for player_id in assumptions.unavailable_player_ids)
        )
    if assumptions.attack_team and assumptions.attack_change:
        labels.append(f"{assumptions.attack_team} attack: {assumptions.attack_change:+.0f}%")
    for label, ids in (
        ("Never sell", assumptions.protected_player_ids),
        ("Must sell", assumptions.must_sell_player_ids),
        ("Must buy", assumptions.must_buy_player_ids),
        ("Exclude", assumptions.excluded_player_ids),
    ):
        if ids:
            labels.append(f"{label}: " + ", ".join(names[player_id] for player_id in ids))
    if assumptions.forced_chip and assumptions.forced_gameweek_id:
        gameweek_names = dict(gameweeks)
        labels.append(
            f"Force {assumptions.forced_chip}: "
            f"{gameweek_names[assumptions.forced_gameweek_id]}"
        )
    return tuple(labels) if labels else ("No forecast assumptions changed",)
