"""Odds import, fixture market forecast, and player market xPts services."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpl_optimizer.database.base import Database
from fpl_optimizer.database.forecast_repository import ForecastRepository
from fpl_optimizer.database.models import Fixture
from fpl_optimizer.database.odds_repository import OddsRepository
from fpl_optimizer.domain.enums import OddsMarket
from fpl_optimizer.domain.forecasts import (
    ExpectedMinutes,
    PlayerForecastInput,
    StatisticalComponents,
)
from fpl_optimizer.domain.markets import (
    ConsensusMarket,
    GoalscorerOddsQuote,
    MarketFixtureOutput,
    OddsQuote,
    PlayerMarketOutput,
)
from fpl_optimizer.features.expected_minutes import project_expected_minutes
from fpl_optimizer.forecasting.statistical import (
    ASSIST_PRIOR_PER_90,
    CLEAN_SHEET_POINTS,
    GOAL_POINTS,
    GOAL_PRIOR_PER_90,
    project_statistical_xpts,
    shrunk_rate_per90,
)
from fpl_optimizer.odds.consensus import build_consensus
from fpl_optimizer.odds.implied_goals import fit_implied_goals
from fpl_optimizer.odds.providers.base import OddsProvider


@dataclass(frozen=True, slots=True)
class OddsImportReport:
    """Summary of a local odds import."""

    received: int
    inserted: int
    total_stored: int


@dataclass(frozen=True, slots=True)
class MarketRunReport:
    """Summary of one market forecast run."""

    fixtures: int
    player_forecasts: int
    prediction_at: datetime
    devig_method: str
    warnings: tuple[str, ...]


@dataclass(slots=True)
class _PlayerAggregate:
    components: StatisticalComponents
    fixtures: list[dict[str, object]]
    count: int
    confidence: str
    cutoff: datetime
    goalscorer_probability: float | None


class OddsImportService:
    """Validate provider output and atomically persist it."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def import_provider(self, provider: OddsProvider) -> OddsImportReport:
        quotes = provider.get_quotes()
        fixture_quotes = [quote for quote in quotes if isinstance(quote, OddsQuote)]
        scorer_quotes = [quote for quote in quotes if isinstance(quote, GoalscorerOddsQuote)]
        imported_at = datetime.now(UTC)
        with self.database.session() as session:
            repository = OddsRepository(session)
            inserted = repository.import_quotes(fixture_quotes, imported_at)
            inserted += repository.import_goalscorer_quotes(scorer_quotes, imported_at)
            session.flush()
            total = repository.quote_count()
        return OddsImportReport(len(quotes), inserted, total)


class MarketService:
    """Generate fixture and player forecasts from stored market snapshots."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def run(self, devig_method: str = "multiplicative") -> MarketRunReport:
        prediction_at = datetime.now(UTC)
        warnings: list[str] = []
        with self.database.session() as session:
            odds_repository = OddsRepository(session)
            grouped_quotes = odds_repository.fixture_quotes()
            outputs: list[MarketFixtureOutput] = []
            for fixture_id, quotes in grouped_quotes.items():
                try:
                    match = build_consensus(quotes, OddsMarket.MATCH_RESULT, devig_method)
                    totals = build_consensus(quotes, OddsMarket.TOTAL_GOALS_2_5, devig_method)
                    btts = _optional_consensus(quotes, OddsMarket.BTTS, devig_method)
                    home_total = _optional_consensus(
                        quotes, OddsMarket.HOME_TOTAL_1_5, devig_method
                    )
                    away_total = _optional_consensus(
                        quotes, OddsMarket.AWAY_TOTAL_1_5, devig_method
                    )
                    goals = fit_implied_goals(match, totals, btts, home_total, away_total)
                except ValueError as error:
                    warnings.append(f"Fixture {quotes[0].fixture_fpl_id}: {error}")
                    continue
                optional_markets = [
                    market for market in (btts, home_total, away_total) if market is not None
                ]
                input_cutoff = max(
                    match.observed_at,
                    totals.observed_at,
                    *(market.observed_at for market in optional_markets),
                )
                outputs.append(
                    MarketFixtureOutput(
                        fixture_id=fixture_id,
                        prediction_at=prediction_at,
                        input_cutoff_at=input_cutoff,
                        home_win=goals.home_win,
                        draw=goals.draw,
                        away_win=goals.away_win,
                        over_2_5=goals.over_2_5,
                        btts_yes=goals.btts_yes,
                        home_over_1_5=goals.home_over_1_5,
                        away_over_1_5=goals.away_over_1_5,
                        home_xg=goals.home_xg,
                        away_xg=goals.away_xg,
                        home_clean_sheet=math.exp(-goals.away_xg),
                        away_clean_sheet=math.exp(-goals.home_xg),
                        dispersion=max(
                            match.dispersion,
                            totals.dispersion,
                            *(market.dispersion for market in optional_markets),
                        ),
                        bookmaker_count=min(match.bookmaker_count, totals.bookmaker_count),
                        fit_residual=goals.residual,
                        fit_success=goals.success,
                        devig_method=devig_method,
                        advanced_market_count=len(optional_markets),
                    )
                )
            if not outputs:
                raise RuntimeError("No fixtures have complete 1X2 and over/under 2.5 markets")
            odds_repository.save_market_forecasts(outputs)
            session.flush()
            player_outputs = _player_market_outputs(session, outputs, prediction_at)
            odds_repository.save_player_market_forecasts(player_outputs)

        return MarketRunReport(
            fixtures=len(outputs),
            player_forecasts=len(player_outputs),
            prediction_at=prediction_at,
            devig_method=devig_method,
            warnings=tuple(warnings),
        )


def _player_market_outputs(
    session: Session,
    markets: list[MarketFixtureOutput],
    prediction_at: datetime,
) -> list[PlayerMarketOutput]:
    forecast_repository = ForecastRepository(session)
    goalscorer_probabilities = OddsRepository(session).goalscorer_probabilities()
    players = forecast_repository.players()
    players_by_team: dict[int, list[PlayerForecastInput]] = {}
    for player in players:
        players_by_team.setdefault(player.team_id, []).append(player)
    matches_played = forecast_repository.team_matches_played()
    minutes: dict[int, ExpectedMinutes] = {
        player.player_id: project_expected_minutes(player, matches_played.get(player.team_id, 0))
        for player in players
    }
    fixtures = {
        fixture.id: fixture
        for fixture in session.scalars(
            select(Fixture).where(Fixture.id.in_([market.fixture_id for market in markets]))
        )
    }
    aggregated: dict[tuple[int, int], _PlayerAggregate] = {}
    for market in markets:
        fixture = fixtures[market.fixture_id]
        if fixture.gameweek_id is None:
            continue
        for team_id, team_xg, opponent_xg, cs_probability, venue in (
            (
                fixture.home_team_id,
                market.home_xg,
                market.away_xg,
                market.home_clean_sheet,
                "H",
            ),
            (
                fixture.away_team_id,
                market.away_xg,
                market.home_xg,
                market.away_clean_sheet,
                "A",
            ),
        ):
            team_players = players_by_team.get(team_id, [])
            scorer_by_player = {
                player.player_id: goalscorer_probabilities[(fixture.id, player.player_id)][0]
                for player in team_players
                if (fixture.id, player.player_id) in goalscorer_probabilities
            }
            goal_weights = _attacking_weights(
                team_players, minutes, "goals", scorer_by_player
            )
            assist_weights = _attacking_weights(team_players, minutes, "assists")
            for player in team_players:
                minute_projection = minutes[player.player_id]
                base, _ = project_statistical_xpts(
                    player,
                    minute_projection,
                    1.0,
                    cs_probability,
                    opponent_xg,
                )
                components = StatisticalComponents(
                    appearance=base.appearance,
                    goals=team_xg * goal_weights[player.player_id] * GOAL_POINTS[player.position],
                    assists=team_xg * 0.75 * assist_weights[player.player_id] * 3.0,
                    clean_sheet=(
                        minute_projection.p_60_plus
                        * cs_probability
                        * CLEAN_SHEET_POINTS[player.position]
                    ),
                    saves=base.saves,
                    bonus=base.bonus,
                    deductions=base.deductions,
                )
                key = (player.player_id, fixture.gameweek_id)
                state = aggregated.setdefault(
                    key,
                    _PlayerAggregate(
                        components=StatisticalComponents(0, 0, 0, 0, 0, 0, 0),
                        fixtures=[],
                        count=0,
                        confidence="High",
                        cutoff=market.input_cutoff_at,
                        goalscorer_probability=None,
                    ),
                )
                state.components = _add(state.components, components)
                state.count += 1
                state.cutoff = max(state.cutoff, market.input_cutoff_at)
                confidence = _market_confidence(market)
                state.confidence = _lower_confidence(state.confidence, confidence)
                scorer = goalscorer_probabilities.get((fixture.id, player.player_id))
                if scorer is not None:
                    state.goalscorer_probability = max(
                        state.goalscorer_probability or 0.0, scorer[0]
                    )
                    state.cutoff = max(state.cutoff, scorer[1])
                state.fixtures.append(
                    {
                        "venue": venue,
                        "team_xg": round(team_xg, 4),
                        "opponent_xg": round(opponent_xg, 4),
                        "clean_sheet_probability": round(cs_probability, 4),
                        "goal_share": round(goal_weights[player.player_id], 4),
                        "assist_share": round(assist_weights[player.player_id], 4),
                        "goalscorer_probability": (
                            round(scorer[0], 4) if scorer is not None else None
                        ),
                        "bookmakers": market.bookmaker_count,
                        "dispersion": round(market.dispersion, 4),
                    }
                )

    return [
        PlayerMarketOutput(
            player_id=player_id,
            gameweek_id=gameweek_id,
            prediction_at=prediction_at,
            input_cutoff_at=state.cutoff,
            components=state.components,
            fixture_count=state.count,
            confidence=state.confidence,
            explanation={
                "model": "advanced-market-xpts 0.9.0",
                "fixtures": state.fixtures,
                "limitations": (
                    "Team market xG is allocated with shrunk player attacking shares; "
                    "optional goalscorer prices refine goal allocation when present."
                ),
            },
            goalscorer_probability=state.goalscorer_probability,
        )
        for (player_id, gameweek_id), state in aggregated.items()
    ]


def _attacking_weights(
    players: list[PlayerForecastInput],
    minutes: dict[int, ExpectedMinutes],
    event: str,
    scorer_probabilities: dict[int, float] | None = None,
) -> dict[int, float]:
    weights: dict[int, float] = {}
    for player in players:
        projection = minutes[player.player_id]
        if event == "goals":
            rate = shrunk_rate_per90(
                player.goals, player.minutes, GOAL_PRIOR_PER_90[player.position]
            )
        else:
            rate = shrunk_rate_per90(
                player.assists, player.minutes, ASSIST_PRIOR_PER_90[player.position]
            )
        weights[player.player_id] = rate * projection.expected_minutes
    total = sum(weights.values())
    if total <= 0:
        baseline = {player.player_id: 1.0 / len(players) for player in players}
    else:
        baseline = {player_id: weight / total for player_id, weight in weights.items()}
    if event != "goals" or not scorer_probabilities:
        return baseline
    scorer_lambdas = {
        player_id: -math.log(max(1.0 - probability, 1e-6))
        for player_id, probability in scorer_probabilities.items()
    }
    scorer_total = sum(scorer_lambdas.values())
    if scorer_total <= 0:
        return baseline
    blended = {
        player.player_id: 0.5 * baseline[player.player_id]
        + 0.5 * scorer_lambdas.get(player.player_id, 0.0) / scorer_total
        for player in players
    }
    normalizer = sum(blended.values())
    return {player_id: value / normalizer for player_id, value in blended.items()}


def _optional_consensus(
    quotes: list[OddsQuote], market: OddsMarket, method: str
) -> ConsensusMarket | None:
    try:
        return build_consensus(quotes, market, method)
    except ValueError:
        return None


def _market_confidence(market: MarketFixtureOutput) -> str:
    if market.bookmaker_count >= 3 and market.dispersion < 0.025 and market.fit_residual < 0.04:
        return "High"
    if market.bookmaker_count >= 2 and market.fit_residual < 0.08:
        return "Medium"
    return "Low"


def _lower_confidence(left: str, right: str) -> str:
    order = {"Low": 0, "Medium": 1, "High": 2}
    return left if order[left] <= order[right] else right


def _add(left: StatisticalComponents, right: StatisticalComponents) -> StatisticalComponents:
    return StatisticalComponents(
        left.appearance + right.appearance,
        left.goals + right.goals,
        left.assists + right.assists,
        left.clean_sheet + right.clean_sheet,
        left.saves + right.saves,
        left.bonus + right.bonus,
        left.deductions + right.deductions,
    )
