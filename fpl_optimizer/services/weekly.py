"""Weekly dashboard orchestration over existing decision engines."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fpl_optimizer.domain.chips import ChipEvaluation, ChipOpportunity
from fpl_optimizer.domain.planner import MultiGameweekPlan
from fpl_optimizer.domain.simulation import SimulationResult
from fpl_optimizer.domain.strategy import StrategyProfile
from fpl_optimizer.domain.team import LineupResult
from fpl_optimizer.domain.transfers import TransferEvaluation, TransferPlanResult
from fpl_optimizer.domain.weekly import ConfidenceFactor, WeeklyDecisionSummary
from fpl_optimizer.services.chips import ChipRunReport, ChipService
from fpl_optimizer.services.planner import MultiGameweekPlannerService, PlannerRunReport
from fpl_optimizer.services.simulation import SimulationRunReport, SimulationService
from fpl_optimizer.services.team import CurrentTeamService, LineupRunReport
from fpl_optimizer.services.transfers import TransferOptimizerService, TransferRunReport
from fpl_optimizer.services.update_team import TeamUpdateReport, TeamUpdateService

DEFAULT_SIMULATION_ITERATIONS = 2_500
DEFAULT_SIMULATION_SEED = 42


@dataclass(frozen=True, slots=True)
class WeeklyDecisionReport:
    """Complete outputs rendered by the weekly dashboard."""

    created_at: datetime
    summary: WeeklyDecisionSummary
    lineup: LineupRunReport
    transfers: TransferRunReport
    planner: PlannerRunReport
    simulation: SimulationRunReport
    chips: ChipRunReport
    update: TeamUpdateReport | None
    warnings: tuple[str, ...]


class WeeklyDecisionService:
    """Run and combine the established weekly decision services."""

    def __init__(
        self,
        update: TeamUpdateService,
        team: CurrentTeamService,
        transfers: TransferOptimizerService,
        planner: MultiGameweekPlannerService,
        simulation: SimulationService,
        chips: ChipService,
    ) -> None:
        self.update = update
        self.team = team
        self.transfers = transfers
        self.planner = planner
        self.simulation = simulation
        self.chips = chips

    def run_live(
        self,
        team_id: int,
        profile: StrategyProfile,
        market_weight: float,
    ) -> WeeklyDecisionReport:
        """Refresh public inputs and produce the complete weekly decision."""

        update = self.update.run(team_id, profile, market_weight)
        return self._finish(
            profile,
            market_weight,
            lineup=update.lineup,
            transfers=update.transfers,
            update=update,
            warnings=update.warnings,
        )

    def run_cached(
        self,
        profile: StrategyProfile,
        market_weight: float,
    ) -> WeeklyDecisionReport:
        """Use already-cached inputs when no public Team ID refresh is desired."""

        lineup = self.team.optimize(profile, market_weight)
        transfers = self.transfers.run(profile, market_weight)
        return self._finish(
            profile,
            market_weight,
            lineup=lineup,
            transfers=transfers,
            update=None,
            warnings=(),
        )

    def _finish(
        self,
        profile: StrategyProfile,
        market_weight: float,
        *,
        lineup: LineupRunReport,
        transfers: TransferRunReport,
        update: TeamUpdateReport | None,
        warnings: tuple[str, ...],
    ) -> WeeklyDecisionReport:
        horizon = min(6, max(2, profile.horizon))
        planner = self.planner.run(profile, market_weight, horizon)
        simulation = self.simulation.run(
            horizon=horizon,
            iterations=DEFAULT_SIMULATION_ITERATIONS,
            seed=DEFAULT_SIMULATION_SEED,
            market_weight=market_weight,
        )
        chips = self.chips.run(profile, market_weight, horizon)
        summary = build_weekly_summary(
            lineup.result,
            transfers.evaluation,
            planner.plan,
            simulation.result,
            chips.evaluation,
            warnings=warnings,
        )
        return WeeklyDecisionReport(
            created_at=datetime.now(UTC),
            summary=summary,
            lineup=lineup,
            transfers=transfers,
            planner=planner,
            simulation=simulation,
            chips=chips,
            update=update,
            warnings=warnings,
        )


def build_weekly_summary(
    lineup: LineupResult,
    transfers: TransferEvaluation,
    planner: MultiGameweekPlan,
    simulation: SimulationResult,
    chips: ChipEvaluation,
    *,
    warnings: tuple[str, ...] = (),
) -> WeeklyDecisionSummary:
    """Combine raw engine outputs into one explainable weekly decision card."""

    recommended = next(
        plan for plan in transfers.plans if plan.transfers == transfers.recommended_transfers
    )
    first_gameweek = planner.weeks[0].gameweek if planner.weeks else None
    chip = _this_week_chip(chips, first_gameweek)
    action = transfers.recommendation
    action_kind = "Transfer"
    rationale = transfers.rationale
    if transfers.recommended_transfers == 0:
        action_kind = "Roll"
    if recommended.hit_cost:
        action_kind = "Hit"
        action = f"{action} · TAKE A -{recommended.hit_cost} HIT"
    if chip is not None and chip.projected_gain >= max(3.0, recommended.net_gain):
        action = f"PLAY {chip.chip.upper()}"
        action_kind = "Chip"
        rationale = chip.rationale

    alternative_plan = _alternative_plan(transfers, recommended)
    alternative = _plan_label(alternative_plan)
    clarity = _decision_clarity(transfers, recommended, alternative_plan)
    lineup_reliability = _lineup_reliability(lineup)
    simulation_certainty = _simulation_certainty(simulation)
    warning_penalty = min(20.0, len(warnings) * 5.0)
    confidence_score = _clamp(
        0.45 * clarity + 0.30 * lineup_reliability + 0.25 * simulation_certainty
        - warning_penalty
    )
    confidence_label = (
        "High" if confidence_score >= 75 else "Medium" if confidence_score >= 55 else "Low"
    )
    risk_score = _risk_score(lineup, simulation)
    risk_label = "Low" if risk_score < 35 else "Medium" if risk_score < 60 else "High"
    captain = next(
        player.player
        for player in lineup.starters
        if player.player_id == lineup.captain_id
    )
    vice = next(
        player.player for player in lineup.starters if player.player_id == lineup.vice_captain_id
    )
    return WeeklyDecisionSummary(
        action=action,
        action_kind=action_kind,
        rationale=rationale,
        alternative=alternative,
        alternative_gain=alternative_plan.net_gain,
        projected_score=lineup.projected_points,
        confidence_score=confidence_score,
        confidence_label=confidence_label,
        risk_score=risk_score,
        risk_label=risk_label,
        recommended_transfers=transfers.recommended_transfers,
        hit_cost=recommended.hit_cost,
        captain=captain,
        vice_captain=vice,
        formation=lineup.formation,
        next_3_squad_xpts=lineup.next_3_squad_xpts,
        next_5_squad_xpts=lineup.next_5_squad_xpts,
        first_gameweek=first_gameweek,
        confidence_factors=(
            ConfidenceFactor(
                "Decision clarity",
                clarity,
                "Separation between the recommended transfer action, the roll threshold, and "
                "the strongest alternative.",
            ),
            ConfidenceFactor(
                "Lineup reliability",
                lineup_reliability,
                "Expected minutes and modeled risk across the recommended starting XI.",
            ),
            ConfidenceFactor(
                "Simulation certainty",
                simulation_certainty,
                "Outcome spread relative to the simulated mean for the current squad.",
            ),
        ),
    )


def _this_week_chip(
    evaluation: ChipEvaluation, first_gameweek: str | None
) -> ChipOpportunity | None:
    if evaluation.best_chip is None or first_gameweek is None:
        return None
    return next(
        (
            opportunity
            for opportunity in evaluation.opportunities
            if opportunity.chip == evaluation.best_chip
            and opportunity.available
            and opportunity.recommended_gameweek == first_gameweek
        ),
        None,
    )


def _alternative_plan(
    evaluation: TransferEvaluation, recommended: TransferPlanResult
) -> TransferPlanResult:
    alternatives = [plan for plan in evaluation.plans if plan.transfers != recommended.transfers]
    return max(alternatives, key=lambda plan: (plan.net_gain, -plan.transfers), default=recommended)


def _plan_label(plan: TransferPlanResult) -> str:
    if plan.transfers == 0:
        return "Roll transfer"
    moves = ", ".join(f"{move.out_player} → {move.in_player}" for move in plan.moves)
    return f"Make {plan.transfers} transfer(s): {moves}"


def _decision_clarity(
    evaluation: TransferEvaluation,
    recommended: TransferPlanResult,
    alternative: TransferPlanResult,
) -> float:
    if recommended.transfers == 0:
        margin = evaluation.roll_flexibility_value - alternative.net_gain
    else:
        margin = min(
            recommended.net_gain - evaluation.roll_flexibility_value,
            recommended.net_gain - alternative.net_gain,
        )
    return _clamp(55.0 + margin * 12.0)


def _lineup_reliability(lineup: LineupResult) -> float:
    values = [
        min(player.expected_minutes / 90.0, 1.0) * (1.0 - player.risk / 100.0)
        for player in lineup.starters
    ]
    return _clamp(100.0 * sum(values) / len(values))


def _simulation_certainty(simulation: SimulationResult) -> float:
    if simulation.mean <= 0:
        return 0.0
    coefficient = simulation.standard_deviation / simulation.mean
    return _clamp(100.0 - coefficient * 180.0)


def _risk_score(lineup: LineupResult, simulation: SimulationResult) -> float:
    lineup_risk = sum(player.risk for player in lineup.starters) / len(lineup.starters)
    outcome_risk = (
        100.0 * simulation.standard_deviation / simulation.mean
        if simulation.mean > 0
        else 100.0
    )
    return _clamp(0.65 * lineup_risk + 0.35 * outcome_risk)


def _clamp(value: float) -> float:
    return min(100.0, max(0.0, value))
