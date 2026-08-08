"""Six-Gameweek statistical forecast orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fpl_optimizer.database.base import Database
from fpl_optimizer.database.forecast_repository import ForecastRepository, ensure_utc
from fpl_optimizer.database.repositories import FplRepository
from fpl_optimizer.domain.forecasts import (
    ExpectedMinutes,
    ForecastFixture,
    ForecastOutput,
    PlayerForecastInput,
    StatisticalComponents,
    TeamStrength,
)
from fpl_optimizer.features.expected_minutes import project_expected_minutes
from fpl_optimizer.features.fixture_strength import (
    StrengthAverages,
    attack_multiplier,
    clean_sheet_probability,
    league_strength_averages,
    opponent_expected_goals,
)
from fpl_optimizer.forecasting.statistical import project_statistical_xpts

MODEL_NAME = "advanced-statistical-xpts"
MODEL_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class ForecastReport:
    """Summary of a completed statistical forecast run."""

    players: int
    gameweeks: int
    forecasts: int
    prediction_at: datetime
    input_cutoff_at: datetime
    model_version: str


class ForecastService:
    """Generate and persist explainable six-Gameweek forecasts."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def run(self, horizon: int = 6) -> ForecastReport:
        """Generate a complete run using one immutable input cutoff."""

        if horizon < 1 or horizon > 6:
            raise ValueError("Forecast horizon must be between 1 and 6 Gameweeks")
        prediction_at = datetime.now(UTC)

        with self.database.session() as session:
            source_repository = FplRepository(session)
            freshness = source_repository.freshness()
            if freshness is None:
                raise RuntimeError("Refresh official FPL data before generating forecasts")
            input_cutoff = ensure_utc(freshness)
            repository = ForecastRepository(session)
            players = repository.players()
            teams = repository.teams()
            gameweeks = repository.upcoming_gameweeks(horizon)
            if not gameweeks:
                raise RuntimeError("No unfinished Gameweeks are available to forecast")

            gameweek_ids = [gameweek.id for gameweek in gameweeks]
            fixtures = repository.fixtures(gameweek_ids)
            fixtures_by_gameweek = _group_fixtures(fixtures)
            matches_played = repository.team_matches_played()
            team_by_id = {team.team_id: team for team in teams}
            averages = league_strength_averages(teams)
            strengths_available = (
                min(
                    averages.attack_home,
                    averages.attack_away,
                    averages.defence_home,
                    averages.defence_away,
                )
                > 0
            )

            outputs: list[ForecastOutput] = []
            for player in players:
                minutes = project_expected_minutes(player, matches_played.get(player.team_id, 0))
                for gameweek in gameweeks:
                    player_fixtures = [
                        fixture
                        for fixture in fixtures_by_gameweek.get(gameweek.id, [])
                        if player.team_id in (fixture.home_team_id, fixture.away_team_id)
                    ]
                    outputs.append(
                        _project_gameweek(
                            player=player,
                            minutes=minutes,
                            gameweek_id=gameweek.id,
                            fixtures=player_fixtures,
                            team_by_id=team_by_id,
                            averages=averages,
                            prediction_at=prediction_at,
                            input_cutoff=input_cutoff,
                            strengths_available=strengths_available,
                        )
                    )

            model = repository.model_version(
                MODEL_NAME,
                MODEL_VERSION,
                parameters={
                    "horizon": horizon,
                    "goal_rate_prior_minutes": 900,
                    "expected_minutes_prior_matches": 3,
                    "expected_minutes_role_signals": "starts-plus-minutes-share",
                    "additional_player_signals": "ict-form-bps-bounded",
                    "scoring_rules": "fpl-2026-27",
                    "defensive_contribution_thresholds": "DEF-10-CBIT;MID-FWD-12-CBIRT",
                    "baseline_team_xg": 1.35,
                    "fixture_strength_source": "official-ratings-with-fdr-fallback",
                },
                created_at=prediction_at,
            )
            repository.save(outputs, model)

        return ForecastReport(
            players=len(players),
            gameweeks=len(gameweeks),
            forecasts=len(outputs),
            prediction_at=prediction_at,
            input_cutoff_at=input_cutoff,
            model_version=MODEL_VERSION,
        )


def _project_gameweek(
    *,
    player: PlayerForecastInput,
    minutes: ExpectedMinutes,
    gameweek_id: int,
    fixtures: list[ForecastFixture],
    team_by_id: dict[int, TeamStrength],
    averages: StrengthAverages,
    prediction_at: datetime,
    input_cutoff: datetime,
    strengths_available: bool,
) -> ForecastOutput:
    total = StatisticalComponents(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    fixture_explanations: list[dict[str, object]] = []
    opponents: list[str] = []

    for fixture in fixtures:
        is_home = fixture.home_team_id == player.team_id
        opponent_id = fixture.away_team_id if is_home else fixture.home_team_id
        team = team_by_id[player.team_id]
        opponent = team_by_id[opponent_id]
        difficulty = fixture.home_difficulty if is_home else fixture.away_difficulty
        opponent_difficulty = fixture.away_difficulty if is_home else fixture.home_difficulty
        player_attack = attack_multiplier(team, opponent, is_home, difficulty, averages)
        opponent_attack = attack_multiplier(
            opponent, team, not is_home, opponent_difficulty, averages
        )
        opponent_xg = opponent_expected_goals(opponent_attack)
        cs_probability = clean_sheet_probability(opponent_attack)
        components, events = project_statistical_xpts(
            player,
            minutes,
            player_attack,
            cs_probability,
            opponent_xg,
        )
        total = _add_components(total, components)
        venue = "H" if is_home else "A"
        opponents.append(f"{opponent.short_name} ({venue})")
        fixture_explanations.append(
            {
                "opponent": opponent.short_name,
                "venue": venue,
                **{key: round(value, 4) for key, value in events.items()},
                "xpts": round(components.total, 4),
            }
        )

    fixture_count = len(fixtures)
    confidence = minutes.confidence
    if not strengths_available:
        confidence = "Low"
    explanation: dict[str, object] = {
        "model": f"{MODEL_NAME} {MODEL_VERSION}",
        "expected_minutes_per_fixture": round(minutes.expected_minutes, 4),
        "p_start": round(minutes.p_start, 4),
        "p_sub_appearance": round(minutes.p_sub_appearance, 4),
        "p_60_plus": round(minutes.p_60_plus, 4),
        "availability": round(minutes.availability, 4),
        "fixtures": fixture_explanations,
        "limitations": (
            "Role and event-rate priors are blended with starts, minutes share, ICT, form, "
            "BPS, and official 2026/27 defensive-action totals. Bonus remains a historical-rate "
            "projection rather than a full event-level BPS simulation."
        ),
    }
    return ForecastOutput(
        player_id=player.player_id,
        gameweek_id=gameweek_id,
        prediction_at=prediction_at,
        input_cutoff_at=input_cutoff,
        expected_minutes=minutes.expected_minutes * fixture_count,
        components=total,
        fixture_count=fixture_count,
        opponent_summary=" + ".join(opponents) if opponents else "Blank",
        confidence=confidence,
        explanation=explanation,
    )


def _group_fixtures(fixtures: list[ForecastFixture]) -> dict[int, list[ForecastFixture]]:
    grouped: dict[int, list[ForecastFixture]] = {}
    for fixture in fixtures:
        grouped.setdefault(fixture.gameweek_id, []).append(fixture)
    return grouped


def _add_components(
    left: StatisticalComponents,
    right: StatisticalComponents,
) -> StatisticalComponents:
    return StatisticalComponents(
        appearance=left.appearance + right.appearance,
        goals=left.goals + right.goals,
        assists=left.assists + right.assists,
        clean_sheet=left.clean_sheet + right.clean_sheet,
        saves=left.saves + right.saves,
        bonus=left.bonus + right.bonus,
        deductions=left.deductions + right.deductions,
        defensive_contribution=(
            left.defensive_contribution + right.defensive_contribution
        ),
    )
