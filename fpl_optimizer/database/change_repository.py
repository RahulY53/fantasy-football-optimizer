"""Read immutable source histories for player change detection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import InstrumentedAttribute, Session

from fpl_optimizer.database.models import (
    Gameweek,
    Player,
    PlayerAvailabilitySnapshot,
    PlayerForecast,
    PlayerMarketForecast,
    PlayerSnapshot,
    Team,
)


@dataclass(frozen=True, slots=True)
class PlayerIdentity:
    player_id: int
    full_name: str
    team: str
    position: str


@dataclass(frozen=True, slots=True)
class OfficialState:
    price: float
    ownership: float
    status: str
    news: str
    chance_next_round: int | None


@dataclass(frozen=True, slots=True)
class ForecastState:
    expected_minutes: float
    xpts: float
    xpts_3gw: float
    xpts_5gw: float


@dataclass(frozen=True, slots=True)
class MarketState:
    xpts: float
    xpts_3gw: float
    xpts_5gw: float
    goal_probability: float | None


@dataclass(frozen=True, slots=True)
class StatePair[T]:
    previous_at: datetime | None
    current_at: datetime | None
    previous: dict[int, T]
    current: dict[int, T]


class ChangeRepository:
    """Load the latest two independent observations from each cached source."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def identities(self) -> dict[int, PlayerIdentity]:
        """Return current canonical player identities."""

        return {
            player.id: PlayerIdentity(player.id, player.full_name, team.short_name, player.position)
            for player, team in self.session.execute(
                select(Player, Team).join(Team, Player.team_id == Team.id)
            )
        }

    def official_states(self) -> StatePair[OfficialState]:
        """Return the latest two official player metric snapshots."""

        times = self._latest_times(PlayerSnapshot.observed_at)
        return StatePair(
            previous_at=times[1] if len(times) > 1 else None,
            current_at=times[0] if times else None,
            previous=self._official_at(times[1]) if len(times) > 1 else {},
            current=self._official_at(times[0]) if times else {},
        )

    def forecast_states(self) -> StatePair[ForecastState]:
        """Return the latest two statistical forecast runs."""

        times = self._latest_times(PlayerForecast.prediction_at)
        return StatePair(
            previous_at=times[1] if len(times) > 1 else None,
            current_at=times[0] if times else None,
            previous=self._forecast_at(times[1]) if len(times) > 1 else {},
            current=self._forecast_at(times[0]) if times else {},
        )

    def market_states(self) -> StatePair[MarketState]:
        """Return the latest two player-level market forecast runs."""

        times = self._latest_times(PlayerMarketForecast.prediction_at)
        return StatePair(
            previous_at=times[1] if len(times) > 1 else None,
            current_at=times[0] if times else None,
            previous=self._market_at(times[1]) if len(times) > 1 else {},
            current=self._market_at(times[0]) if times else {},
        )

    def _latest_times(self, column: InstrumentedAttribute[datetime]) -> list[datetime]:
        statement = select(column).distinct().order_by(column.desc()).limit(2)
        return list(self.session.scalars(statement))

    def _official_at(self, observed_at: datetime) -> dict[int, OfficialState]:
        availability = {
            row.player_id: row
            for row in self.session.scalars(
                select(PlayerAvailabilitySnapshot).where(
                    PlayerAvailabilitySnapshot.observed_at == observed_at
                )
            )
        }
        return {
            row.player_id: OfficialState(
                price=row.price_tenths / 10.0,
                ownership=row.selected_pct,
                status=availability[row.player_id].status if row.player_id in availability else "",
                news=availability[row.player_id].news if row.player_id in availability else "",
                chance_next_round=(
                    availability[row.player_id].chance_next_round
                    if row.player_id in availability
                    else None
                ),
            )
            for row in self.session.scalars(
                select(PlayerSnapshot).where(PlayerSnapshot.observed_at == observed_at)
            )
        }

    def _forecast_at(self, prediction_at: datetime) -> dict[int, ForecastState]:
        statement = (
            select(PlayerForecast, Gameweek)
            .join(Gameweek, PlayerForecast.gameweek_id == Gameweek.id)
            .where(PlayerForecast.prediction_at == prediction_at)
            .order_by(PlayerForecast.player_id, Gameweek.fpl_id)
        )
        grouped: dict[int, list[PlayerForecast]] = {}
        for forecast, _ in self.session.execute(statement):
            grouped.setdefault(forecast.player_id, []).append(forecast)
        return {
            player_id: ForecastState(
                expected_minutes=rows[0].expected_minutes,
                xpts=rows[0].stat_xpts,
                xpts_3gw=sum(row.stat_xpts for row in rows[:3]),
                xpts_5gw=sum(row.stat_xpts for row in rows[:5]),
            )
            for player_id, rows in grouped.items()
            if rows
        }

    def _market_at(self, prediction_at: datetime) -> dict[int, MarketState]:
        statement = (
            select(PlayerMarketForecast, Gameweek)
            .join(Gameweek, PlayerMarketForecast.gameweek_id == Gameweek.id)
            .where(PlayerMarketForecast.prediction_at == prediction_at)
            .order_by(PlayerMarketForecast.player_id, Gameweek.fpl_id)
        )
        grouped: dict[int, list[PlayerMarketForecast]] = {}
        for forecast, _ in self.session.execute(statement):
            grouped.setdefault(forecast.player_id, []).append(forecast)
        return {
            player_id: MarketState(
                xpts=rows[0].market_xpts,
                xpts_3gw=sum(row.market_xpts for row in rows[:3]),
                xpts_5gw=sum(row.market_xpts for row in rows[:5]),
                goal_probability=rows[0].goalscorer_probability,
            )
            for player_id, rows in grouped.items()
            if rows
        }
