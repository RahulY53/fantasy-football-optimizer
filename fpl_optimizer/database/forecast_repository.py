"""Persistence and read models for Phase 2 statistical forecasts."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fpl_optimizer.database.models import (
    Fixture,
    Gameweek,
    ModelVersion,
    Player,
    PlayerForecast,
    PlayerMarketForecast,
    PlayerSnapshot,
    Team,
)
from fpl_optimizer.domain.enums import Position
from fpl_optimizer.domain.forecasts import (
    ForecastFixture,
    ForecastOutput,
    PlayerForecastInput,
    TeamStrength,
)
from fpl_optimizer.domain.names import resolved_player_name
from fpl_optimizer.domain.simulation import SimulationWeekInput


class ForecastRepository:
    """Load canonical forecast inputs and persist versioned outputs."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def players(self) -> list[PlayerForecastInput]:
        """Return every player joined to the latest observed metrics."""

        latest = (
            select(
                PlayerSnapshot.player_id,
                func.max(PlayerSnapshot.observed_at).label("observed_at"),
            )
            .group_by(PlayerSnapshot.player_id)
            .subquery()
        )
        statement = (
            select(Player, PlayerSnapshot)
            .join(PlayerSnapshot, PlayerSnapshot.player_id == Player.id)
            .join(
                latest,
                (latest.c.player_id == PlayerSnapshot.player_id)
                & (latest.c.observed_at == PlayerSnapshot.observed_at),
            )
        )
        return [
            PlayerForecastInput(
                player_id=player.id,
                fpl_id=player.fpl_id,
                team_id=player.team_id,
                position=Position(player.position),
                web_name=player.web_name,
                status=player.status,
                chance_next_round=player.chance_next_round,
                minutes=metrics.minutes,
                starts=metrics.starts,
                goals=metrics.goals,
                assists=metrics.assists,
                saves=metrics.saves,
                bonus=metrics.bonus,
                price_tenths=metrics.price_tenths,
                total_points=metrics.total_points,
                clean_sheets=metrics.clean_sheets,
                bps=metrics.bps,
                selected_pct=metrics.selected_pct,
                transfers_in=metrics.transfers_in,
                transfers_out=metrics.transfers_out,
                form=metrics.form,
                points_per_game=metrics.points_per_game,
                ict_index=metrics.ict_index,
                own_goals=metrics.own_goals,
                penalties_saved=metrics.penalties_saved,
                penalties_missed=metrics.penalties_missed,
                yellow_cards=metrics.yellow_cards,
                red_cards=metrics.red_cards,
                clearances_blocks_interceptions=metrics.clearances_blocks_interceptions,
                tackles=metrics.tackles,
                recoveries=metrics.recoveries,
                defensive_contribution=metrics.defensive_contribution,
            )
            for player, metrics in self.session.execute(statement)
        ]

    def teams(self) -> list[TeamStrength]:
        """Return team strength inputs."""

        return [
            TeamStrength(
                team_id=team.id,
                name=team.name,
                short_name=team.short_name,
                attack_home=team.strength_attack_home,
                attack_away=team.strength_attack_away,
                defence_home=team.strength_defence_home,
                defence_away=team.strength_defence_away,
            )
            for team in self.session.scalars(select(Team).order_by(Team.id))
        ]

    def upcoming_gameweeks(self, horizon: int) -> list[Gameweek]:
        """Return the next unfinished Gameweeks in official order."""

        return list(
            self.session.scalars(
                select(Gameweek)
                .where(Gameweek.finished.is_(False))
                .order_by(Gameweek.fpl_id)
                .limit(horizon)
            )
        )

    def fixtures(self, gameweek_ids: list[int]) -> list[ForecastFixture]:
        """Return future fixtures assigned to the selected Gameweeks."""

        if not gameweek_ids:
            return []
        statement = select(Fixture).where(Fixture.gameweek_id.in_(gameweek_ids))
        return [
            ForecastFixture(
                fixture_id=fixture.id,
                gameweek_id=fixture.gameweek_id,
                home_team_id=fixture.home_team_id,
                away_team_id=fixture.away_team_id,
                home_difficulty=fixture.home_difficulty,
                away_difficulty=fixture.away_difficulty,
            )
            for fixture in self.session.scalars(statement)
            if fixture.gameweek_id is not None
        ]

    def team_matches_played(self) -> dict[int, int]:
        """Count completed fixtures for each team."""

        counts: dict[int, int] = {}
        finished = self.session.scalars(select(Fixture).where(Fixture.status == "finished"))
        for fixture in finished:
            counts[fixture.home_team_id] = counts.get(fixture.home_team_id, 0) + 1
            counts[fixture.away_team_id] = counts.get(fixture.away_team_id, 0) + 1
        return counts

    def model_version(
        self,
        name: str,
        semantic_version: str,
        parameters: dict[str, object],
        created_at: datetime,
    ) -> ModelVersion:
        """Return the immutable model version row, creating it when necessary."""

        existing = self.session.scalar(
            select(ModelVersion).where(
                ModelVersion.name == name,
                ModelVersion.semantic_version == semantic_version,
            )
        )
        if existing is not None:
            return existing
        row = ModelVersion(
            name=name,
            semantic_version=semantic_version,
            feature_schema="fpl-2026-v1",
            parameter_json=json.dumps(parameters, sort_keys=True),
            training_cutoff_at=None,
            code_revision="local",
            created_at=created_at,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def save(self, outputs: list[ForecastOutput], model_version: ModelVersion) -> None:
        """Persist one complete forecast run."""

        for output in outputs:
            components = output.components
            self.session.add(
                PlayerForecast(
                    player_id=output.player_id,
                    gameweek_id=output.gameweek_id,
                    model_version_id=model_version.id,
                    prediction_at=output.prediction_at,
                    input_cutoff_at=output.input_cutoff_at,
                    expected_minutes=output.expected_minutes,
                    appearance_xpts=components.appearance,
                    goal_xpts=components.goals,
                    assist_xpts=components.assists,
                    clean_sheet_xpts=components.clean_sheet,
                    save_xpts=components.saves,
                    bonus_xpts=components.bonus,
                    deduction_xpts=components.deductions,
                    defensive_contribution_xpts=components.defensive_contribution,
                    stat_xpts=components.total,
                    fixture_count=output.fixture_count,
                    opponent_summary=output.opponent_summary,
                    confidence=output.confidence,
                    component_json=json.dumps(output.explanation, sort_keys=True),
                )
            )

    def latest_prediction_at(self) -> datetime | None:
        """Return the timestamp of the most recent forecast run."""

        return self.session.scalar(select(func.max(PlayerForecast.prediction_at)))

    def latest_market_prediction_at(self) -> datetime | None:
        """Return the timestamp of the most recent player-level market forecast."""

        return self.session.scalar(select(func.max(PlayerMarketForecast.prediction_at)))

    def list_player_summaries(self, market_weight: float = 0.3) -> list[dict[str, object]]:
        """Return current-run 1/3/6 Gameweek player forecast summaries."""

        if not 0.0 <= market_weight <= 1.0:
            raise ValueError("Market weight must be between 0 and 1")
        latest = self.latest_prediction_at()
        if latest is None:
            return []
        statement = (
            select(PlayerForecast, Gameweek)
            .join(Gameweek, PlayerForecast.gameweek_id == Gameweek.id)
            .where(PlayerForecast.prediction_at == latest)
            .order_by(PlayerForecast.player_id, Gameweek.fpl_id)
        )
        grouped: dict[int, list[tuple[PlayerForecast, Gameweek]]] = {}
        for forecast, gameweek in self.session.execute(statement):
            grouped.setdefault(forecast.player_id, []).append((forecast, gameweek))

        market_latest = self.session.scalar(select(func.max(PlayerMarketForecast.prediction_at)))
        market_by_key: dict[tuple[int, int], PlayerMarketForecast] = {}
        if market_latest is not None:
            market_by_key = {
                (forecast.player_id, forecast.gameweek_id): forecast
                for forecast in self.session.scalars(
                    select(PlayerMarketForecast).where(
                        PlayerMarketForecast.prediction_at == market_latest
                    )
                )
            }

        summaries: list[dict[str, object]] = []
        for player_id, rows in grouped.items():
            forecasts = [row[0] for row in rows]
            first = forecasts[0]
            first_explanation = json.loads(first.component_json)
            market_forecasts = [
                market_by_key.get((item.player_id, item.gameweek_id)) for item in forecasts
            ]
            blended = [
                _blend(item.stat_xpts, market.market_xpts if market else None, market_weight)
                for item, market in zip(forecasts, market_forecasts, strict=True)
            ]
            first_market = market_forecasts[0]
            summaries.append(
                {
                    "Player ID": player_id,
                    "Opponent": first.opponent_summary,
                    "Expected minutes": first.expected_minutes,
                    "Start probability %": float(first_explanation.get("p_start", 0.0)) * 100.0,
                    "Stat xPts": first.stat_xpts,
                    "Market xPts": first_market.market_xpts if first_market else None,
                    "Goalscorer probability": (
                        first_market.goalscorer_probability if first_market else None
                    ),
                    "Goal probability %": (
                        first_market.goalscorer_probability * 100.0
                        if first_market and first_market.goalscorer_probability is not None
                        else None
                    ),
                    "Blended xPts": blended[0],
                    "Market edge": (
                        first_market.market_xpts - first.stat_xpts if first_market else None
                    ),
                    "Attacking xPts": _blend(
                        first.goal_xpts + first.assist_xpts,
                        (
                            first_market.goal_xpts + first_market.assist_xpts
                            if first_market
                            else None
                        ),
                        market_weight,
                    ),
                    "Goal xPts": _blend_component(
                        first.goal_xpts,
                        first_market.goal_xpts if first_market else None,
                        market_weight,
                    ),
                    "Assist xPts": _blend_component(
                        first.assist_xpts,
                        first_market.assist_xpts if first_market else None,
                        market_weight,
                    ),
                    "Clean sheet xPts": _blend_component(
                        first.clean_sheet_xpts,
                        first_market.clean_sheet_xpts if first_market else None,
                        market_weight,
                    ),
                    "Save xPts": _blend_component(
                        first.save_xpts,
                        first_market.save_xpts if first_market else None,
                        market_weight,
                    ),
                    "Bonus xPts": _blend_component(
                        first.bonus_xpts,
                        first_market.bonus_xpts if first_market else None,
                        market_weight,
                    ),
                    "Defensive contribution xPts": _blend(
                        first.defensive_contribution_xpts,
                        (
                            first_market.defensive_contribution_xpts
                            if first_market
                            else None
                        ),
                        market_weight,
                    ),
                    "3GW xPts": sum(blended[:3]),
                    "5GW xPts": sum(blended[:5]),
                    "6GW xPts": sum(blended[:6]),
                    "Market coverage": sum(item is not None for item in market_forecasts),
                    "Forecast confidence": first.confidence,
                    "Forecasted": latest,
                }
            )
        return summaries

    def player_details(self, player_id: int, market_weight: float = 0.3) -> list[dict[str, object]]:
        """Return component-level current-run forecasts for one player."""

        return self.player_comparison_details({player_id}, market_weight).get(player_id, [])

    def player_comparison_details(
        self, player_ids: set[int], market_weight: float = 0.3
    ) -> dict[int, list[dict[str, object]]]:
        """Return aligned current-run Gameweek forecasts for selected players."""

        if not 0.0 <= market_weight <= 1.0:
            raise ValueError("Market weight must be between 0 and 1")
        if not player_ids:
            return {}

        latest = self.latest_prediction_at()
        if latest is None:
            return {}
        statement = (
            select(PlayerForecast, Gameweek, Player)
            .join(Gameweek, PlayerForecast.gameweek_id == Gameweek.id)
            .join(Player, PlayerForecast.player_id == Player.id)
            .where(
                PlayerForecast.player_id.in_(player_ids),
                PlayerForecast.prediction_at == latest,
            )
            .order_by(PlayerForecast.player_id, Gameweek.fpl_id)
        )
        market_latest = self.session.scalar(select(func.max(PlayerMarketForecast.prediction_at)))
        market_by_key: dict[tuple[int, int], PlayerMarketForecast] = {}
        if market_latest is not None:
            market_by_key = {
                (forecast.player_id, forecast.gameweek_id): forecast
                for forecast in self.session.scalars(
                    select(PlayerMarketForecast).where(
                        PlayerMarketForecast.player_id.in_(player_ids),
                        PlayerMarketForecast.prediction_at == market_latest,
                    )
                )
            }

        forecast_rows = list(self.session.execute(statement))
        gameweek_ids = {gameweek.id for _, gameweek, _ in forecast_rows}
        teams = {team.id: team for team in self.session.scalars(select(Team))}
        fixtures_by_gameweek: dict[int, list[Fixture]] = {}
        for fixture in self.session.scalars(
            select(Fixture).where(Fixture.gameweek_id.in_(gameweek_ids))
        ):
            if fixture.gameweek_id is not None:
                fixtures_by_gameweek.setdefault(fixture.gameweek_id, []).append(fixture)
        attack_strengths = [
            float(value)
            for team in teams.values()
            for value in (team.strength_attack_home, team.strength_attack_away)
        ]
        defence_strengths = [
            float(value)
            for team in teams.values()
            for value in (team.strength_defence_home, team.strength_defence_away)
        ]

        details: dict[int, list[dict[str, object]]] = {}
        for forecast, gameweek, player in forecast_rows:
            market = market_by_key.get((forecast.player_id, forecast.gameweek_id))
            attacking_difficulty, defensive_difficulty = _fixture_strengths(
                player.team_id,
                fixtures_by_gameweek.get(gameweek.id, []),
                teams,
                attack_strengths,
                defence_strengths,
            )
            details.setdefault(forecast.player_id, []).append(
                {
                    "Gameweek ID": gameweek.id,
                    "Gameweek number": gameweek.fpl_id,
                    "Gameweek": gameweek.name,
                    "Opponent": forecast.opponent_summary,
                    "Fixtures": forecast.fixture_count,
                    "Attacking difficulty": attacking_difficulty,
                    "Defensive difficulty": defensive_difficulty,
                    "Expected minutes": forecast.expected_minutes,
                    "Appearance": forecast.appearance_xpts,
                    "Goals": forecast.goal_xpts,
                    "Assists": forecast.assist_xpts,
                    "Clean sheet": forecast.clean_sheet_xpts,
                    "Saves": forecast.save_xpts,
                    "Bonus": forecast.bonus_xpts,
                    "Defensive contribution": forecast.defensive_contribution_xpts,
                    "Deductions": forecast.deduction_xpts,
                    "Stat xPts": forecast.stat_xpts,
                    "Market xPts": market.market_xpts if market else None,
                    "Goalscorer probability": (
                        market.goalscorer_probability if market else None
                    ),
                    "Blended xPts": _blend(
                        forecast.stat_xpts, market.market_xpts if market else None, market_weight
                    ),
                    "Market edge": (market.market_xpts - forecast.stat_xpts if market else None),
                    "Confidence": forecast.confidence,
                    "Explanation": json.loads(forecast.component_json),
                    "Market explanation": (json.loads(market.component_json) if market else None),
                    "Input cutoff": forecast.input_cutoff_at,
                    "Forecasted": latest,
                }
            )
        return details

    def planning_matrix(
        self, horizon: int, market_weight: float = 0.3
    ) -> tuple[list[tuple[int, str]], dict[int, tuple[float, ...]]]:
        """Return aligned per-Gameweek blended xPts for multi-period planning."""

        if not 2 <= horizon <= 6:
            raise ValueError("Planning horizon must be between two and six Gameweeks")
        if not 0.0 <= market_weight <= 1.0:
            raise ValueError("Market weight must be between 0 and 1")
        latest = self.latest_prediction_at()
        if latest is None:
            return [], {}
        gameweeks = list(
            self.session.scalars(
                select(Gameweek)
                .join(PlayerForecast, PlayerForecast.gameweek_id == Gameweek.id)
                .where(PlayerForecast.prediction_at == latest)
                .distinct()
                .order_by(Gameweek.fpl_id)
                .limit(horizon)
            )
        )
        if len(gameweeks) != horizon:
            return [], {}
        gameweek_ids = [gameweek.id for gameweek in gameweeks]
        forecasts = list(
            self.session.scalars(
                select(PlayerForecast).where(
                    PlayerForecast.prediction_at == latest,
                    PlayerForecast.gameweek_id.in_(gameweek_ids),
                )
            )
        )
        market_latest = self.session.scalar(select(func.max(PlayerMarketForecast.prediction_at)))
        markets: dict[tuple[int, int], PlayerMarketForecast] = {}
        if market_latest is not None:
            markets = {
                (row.player_id, row.gameweek_id): row
                for row in self.session.scalars(
                    select(PlayerMarketForecast).where(
                        PlayerMarketForecast.prediction_at == market_latest,
                        PlayerMarketForecast.gameweek_id.in_(gameweek_ids),
                    )
                )
            }
        by_player: dict[int, dict[int, float]] = {}
        for forecast in forecasts:
            market = markets.get((forecast.player_id, forecast.gameweek_id))
            by_player.setdefault(forecast.player_id, {})[forecast.gameweek_id] = _blend(
                forecast.stat_xpts,
                market.market_xpts if market else None,
                market_weight,
            )
        matrix = {
            player_id: tuple(values[gameweek_id] for gameweek_id in gameweek_ids)
            for player_id, values in by_player.items()
            if all(gameweek_id in values for gameweek_id in gameweek_ids)
        }
        return [(gameweek.id, gameweek.name) for gameweek in gameweeks], matrix

    def simulation_inputs(
        self,
        player_ids: set[int],
        horizon: int,
        market_weight: float,
    ) -> tuple[datetime | None, dict[int, tuple[SimulationWeekInput, ...]]]:
        """Return aligned blended component inputs for current-team simulation."""

        if not 1 <= horizon <= 6:
            raise ValueError("Simulation horizon must be between one and six Gameweeks")
        if not 0.0 <= market_weight <= 1.0:
            raise ValueError("Market weight must be between 0 and 1")
        latest = self.latest_prediction_at()
        if latest is None:
            return None, {}
        statement = (
            select(PlayerForecast, Gameweek)
            .join(Gameweek, PlayerForecast.gameweek_id == Gameweek.id)
            .where(
                PlayerForecast.prediction_at == latest,
                PlayerForecast.player_id.in_(player_ids),
            )
            .order_by(PlayerForecast.player_id, Gameweek.fpl_id)
        )
        statistical: dict[int, list[tuple[PlayerForecast, Gameweek]]] = {}
        for forecast, gameweek in self.session.execute(statement):
            statistical.setdefault(forecast.player_id, []).append((forecast, gameweek))
        market_latest = self.session.scalar(select(func.max(PlayerMarketForecast.prediction_at)))
        markets: dict[tuple[int, int], PlayerMarketForecast] = {}
        if market_latest is not None:
            markets = {
                (row.player_id, row.gameweek_id): row
                for row in self.session.scalars(
                    select(PlayerMarketForecast).where(
                        PlayerMarketForecast.prediction_at == market_latest,
                        PlayerMarketForecast.player_id.in_(player_ids),
                    )
                )
            }
        result: dict[int, tuple[SimulationWeekInput, ...]] = {}
        for player_id, rows in statistical.items():
            weeks: list[SimulationWeekInput] = []
            for forecast, gameweek in rows[:horizon]:
                market = markets.get((player_id, gameweek.id))
                explanation = json.loads(forecast.component_json)
                fixture_count = forecast.fixture_count
                p_start = float(explanation.get("p_start", 0.0)) if fixture_count else 0.0
                p_sub = (
                    float(explanation.get("p_sub_appearance", 0.0))
                    if fixture_count
                    else 0.0
                )
                p_60 = float(explanation.get("p_60_plus", 0.0)) if fixture_count else 0.0
                weeks.append(
                    SimulationWeekInput(
                        gameweek_id=gameweek.id,
                        gameweek=gameweek.name,
                        expected_minutes=forecast.expected_minutes,
                        p_appearance=min(p_start + p_sub, 1.0),
                        p_60_plus=min(p_60, 1.0),
                        appearance_xpts=_blend_component(
                            forecast.appearance_xpts,
                            market.appearance_xpts if market else None,
                            market_weight,
                        ),
                        goal_xpts=_blend_component(
                            forecast.goal_xpts,
                            market.goal_xpts if market else None,
                            market_weight,
                        ),
                        assist_xpts=_blend_component(
                            forecast.assist_xpts,
                            market.assist_xpts if market else None,
                            market_weight,
                        ),
                        clean_sheet_xpts=_blend_component(
                            forecast.clean_sheet_xpts,
                            market.clean_sheet_xpts if market else None,
                            market_weight,
                        ),
                        save_xpts=_blend_component(
                            forecast.save_xpts,
                            market.save_xpts if market else None,
                            market_weight,
                        ),
                        bonus_xpts=_blend_component(
                            forecast.bonus_xpts,
                            market.bonus_xpts if market else None,
                            market_weight,
                        ),
                        defensive_contribution_xpts=_blend_component(
                            forecast.defensive_contribution_xpts,
                            (
                                market.defensive_contribution_xpts
                                if market
                                else None
                            ),
                            market_weight,
                        ),
                        deduction_xpts=_blend_component(
                            forecast.deduction_xpts,
                            market.deduction_xpts if market else None,
                            market_weight,
                        ),
                    )
                )
            if len(weeks) == horizon:
                result[player_id] = tuple(weeks)
        return latest, result

    def player_choices(self) -> list[tuple[int, str, str, str]]:
        """Return player IDs, full names, teams, and positions for selectors."""

        result = self.session.execute(
            select(Player, Team.short_name)
            .join(Team, Player.team_id == Team.id)
            .order_by(Player.display_name, Team.short_name)
        )
        return [
            (
                player.id,
                resolved_player_name(
                    player.display_name,
                    player.first_name,
                    player.second_name,
                    player.web_name,
                ),
                short_name,
                player.position,
            )
            for player, short_name in result
        ]


def ensure_utc(value: datetime) -> datetime:
    """Attach UTC to SQLite-naive timestamps."""

    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _blend(statistical: float, market: float | None, market_weight: float) -> float:
    if market is None:
        return statistical
    return (1.0 - market_weight) * statistical + market_weight * market


def _blend_component(statistical: float, market: float | None, market_weight: float) -> float:
    return _blend(statistical, market, market_weight)


def _fixture_strengths(
    team_id: int,
    fixtures: list[Fixture],
    teams: dict[int, Team],
    attack_strengths: list[float],
    defence_strengths: list[float],
) -> tuple[float | None, float | None]:
    """Return average 1–5 attacking and defensive difficulty for a Gameweek."""

    attacking: list[float] = []
    defensive: list[float] = []
    for fixture in fixtures:
        if fixture.home_team_id == team_id:
            opponent = teams.get(fixture.away_team_id)
            if opponent is not None:
                attacking.append(
                    _strength_rating(opponent.strength_defence_away, defence_strengths)
                )
                defensive.append(
                    _strength_rating(opponent.strength_attack_away, attack_strengths)
                )
        elif fixture.away_team_id == team_id:
            opponent = teams.get(fixture.home_team_id)
            if opponent is not None:
                attacking.append(
                    _strength_rating(opponent.strength_defence_home, defence_strengths)
                )
                defensive.append(
                    _strength_rating(opponent.strength_attack_home, attack_strengths)
                )
    if not attacking or not defensive:
        return None, None
    return sum(attacking) / len(attacking), sum(defensive) / len(defensive)


def _strength_rating(value: int, universe: list[float]) -> float:
    """Scale an official FPL team-strength value to a transparent 1–5 rating."""

    lowest = min(universe)
    highest = max(universe)
    if highest == lowest:
        return 3.0
    return 1.0 + 4.0 * (float(value) - lowest) / (highest - lowest)
