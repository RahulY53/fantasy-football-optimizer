"""Persistence and forecast inputs for the user strategy layer."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from fpl_optimizer.database.models import (
    Fixture,
    Gameweek,
    Player,
    PlayerForecast,
    PlayerMarketForecast,
    PlayerSnapshot,
    Strategy,
    StrategyWeight,
    Team,
)
from fpl_optimizer.domain.strategy import PlayerStrategyInput, StrategyProfile


class StrategyRepository:
    """Load score inputs and save named local strategy profiles."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def player_inputs(self, market_weight: float, horizon: int) -> list[PlayerStrategyInput]:
        """Return raw player features for the selected forecast blend and horizon."""

        if not 0.0 <= market_weight <= 1.0:
            raise ValueError("Market weight must be between 0 and 1")
        if not 1 <= horizon <= 6:
            raise ValueError("Planning horizon must be between 1 and 6 Gameweeks")
        latest = self.session.scalar(select(func.max(PlayerForecast.prediction_at)))
        if latest is None:
            return []
        latest_snapshot = (
            select(
                PlayerSnapshot.player_id,
                func.max(PlayerSnapshot.observed_at).label("observed_at"),
            )
            .group_by(PlayerSnapshot.player_id)
            .subquery()
        )
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
        gameweek_ids = [gameweek.id for gameweek in gameweeks]
        if not gameweek_ids:
            return []
        statement = (
            select(Player, Team, PlayerSnapshot, PlayerForecast, Gameweek)
            .join(Team, Player.team_id == Team.id)
            .join(PlayerSnapshot, PlayerSnapshot.player_id == Player.id)
            .join(
                latest_snapshot,
                (latest_snapshot.c.player_id == PlayerSnapshot.player_id)
                & (latest_snapshot.c.observed_at == PlayerSnapshot.observed_at),
            )
            .join(PlayerForecast, PlayerForecast.player_id == Player.id)
            .join(Gameweek, PlayerForecast.gameweek_id == Gameweek.id)
            .where(
                PlayerForecast.prediction_at == latest,
                PlayerForecast.gameweek_id.in_(gameweek_ids),
            )
            .order_by(Player.id, Gameweek.fpl_id)
        )
        market_latest = self.session.scalar(select(func.max(PlayerMarketForecast.prediction_at)))
        market_by_key: dict[tuple[int, int], PlayerMarketForecast] = {}
        if market_latest is not None:
            market_by_key = {
                (row.player_id, row.gameweek_id): row
                for row in self.session.scalars(
                    select(PlayerMarketForecast).where(
                        PlayerMarketForecast.prediction_at == market_latest,
                        PlayerMarketForecast.gameweek_id.in_(gameweek_ids),
                    )
                )
            }
        fixture_quality = self._fixture_quality(gameweek_ids)
        grouped: dict[int, list[tuple[Player, Team, PlayerSnapshot, PlayerForecast]]] = {}
        for player, team, snapshot, forecast, _ in self.session.execute(statement):
            grouped.setdefault(player.id, []).append((player, team, snapshot, forecast))

        inputs: list[PlayerStrategyInput] = []
        for player_id, rows in grouped.items():
            player, team, snapshot, _ = rows[0]
            weekly: list[float] = []
            attacking = clean_sheet = bonus = 0.0
            minutes = fixtures = confidence = 0.0
            for _, _, _, forecast in rows:
                market = market_by_key.get((player_id, forecast.gameweek_id))
                weekly.append(
                    _blend(
                        forecast.stat_xpts,
                        market.market_xpts if market else None,
                        market_weight,
                    )
                )
                attacking += _blend_components(
                    forecast.goal_xpts + forecast.assist_xpts,
                    (market.goal_xpts + market.assist_xpts) if market else None,
                    market_weight,
                )
                clean_sheet += _blend_components(
                    forecast.clean_sheet_xpts,
                    market.clean_sheet_xpts if market else None,
                    market_weight,
                )
                bonus += _blend_components(
                    forecast.bonus_xpts,
                    market.bonus_xpts if market else None,
                    market_weight,
                )
                minutes += forecast.expected_minutes
                fixtures += forecast.fixture_count
                confidence += {"Low": 0.25, "Medium": 0.65, "High": 1.0}.get(
                    forecast.confidence, 0.25
                )
            inputs.append(
                PlayerStrategyInput(
                    player_id=player_id,
                    player=player.web_name,
                    position=player.position,
                    team=team.short_name,
                    price=snapshot.price_tenths / 10,
                    ownership=snapshot.selected_pct,
                    form=snapshot.form,
                    status=player.status,
                    chance_next_round=player.chance_next_round,
                    horizon_xpts=sum(weekly),
                    week_xpts=tuple(weekly),
                    expected_minutes=minutes / fixtures if fixtures else 0.0,
                    fixture_quality=fixture_quality.get(player.team_id, 0.0),
                    attacking_xpts=attacking,
                    clean_sheet_xpts=clean_sheet,
                    bonus_xpts=bonus,
                    confidence=confidence / len(rows),
                )
            )
        return inputs

    def save(self, profile: StrategyProfile) -> Strategy:
        """Create or replace a named strategy and its raw weights."""

        now = datetime.now(UTC)
        row = self.session.scalar(select(Strategy).where(Strategy.name == profile.name))
        if row is None:
            row = Strategy(
                name=profile.name,
                mode=profile.mode,
                preset_name=profile.preset,
                horizon=profile.horizon,
                risk_appetite=profile.risk_appetite,
                transfer_reluctance=profile.transfer_reluctance,
                ownership_preference=profile.ownership_preference,
                created_at=now,
                updated_at=now,
            )
            self.session.add(row)
            self.session.flush()
        row.mode = profile.mode
        row.preset_name = profile.preset
        row.horizon = profile.horizon
        row.risk_appetite = profile.risk_appetite
        row.transfer_reluctance = profile.transfer_reluctance
        row.ownership_preference = profile.ownership_preference
        row.updated_at = now
        self.session.execute(delete(StrategyWeight).where(StrategyWeight.strategy_id == row.id))
        self.session.add_all(
            StrategyWeight(strategy_id=row.id, feature=feature, raw_weight=weight)
            for feature, weight in profile.weights.items()
        )
        return row

    def list_saved(self) -> list[dict[str, object]]:
        """Return named local strategies with their raw weights."""

        rows = list(self.session.scalars(select(Strategy).order_by(Strategy.updated_at.desc())))
        return [
            {
                "Name": row.name,
                "Mode": row.mode.title(),
                "Preset": row.preset_name,
                "Horizon": row.horizon,
                "Risk appetite": row.risk_appetite,
                "Transfer reluctance": row.transfer_reluctance,
                "Ownership preference": row.ownership_preference,
                "Weights": {weight.feature: weight.raw_weight for weight in row.weights},
                "Updated": row.updated_at,
            }
            for row in rows
        ]

    def _fixture_quality(self, gameweek_ids: list[int]) -> dict[int, float]:
        values: dict[int, list[float]] = {}
        fixtures = self.session.scalars(
            select(Fixture).where(Fixture.gameweek_id.in_(gameweek_ids))
        )
        for fixture in fixtures:
            values.setdefault(fixture.home_team_id, []).append(6.0 - fixture.home_difficulty)
            values.setdefault(fixture.away_team_id, []).append(6.0 - fixture.away_difficulty)
        return {
            team_id: sum(team_values) / len(team_values)
            for team_id, team_values in values.items()
        }


def _blend(statistical: float, market: float | None, market_weight: float) -> float:
    return _blend_components(statistical, market, market_weight)


def _blend_components(statistical: float, market: float | None, market_weight: float) -> float:
    if market is None:
        return statistical
    return (1.0 - market_weight) * statistical + market_weight * market
