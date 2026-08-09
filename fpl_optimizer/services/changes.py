"""Application service for cross-source player change detection."""

from __future__ import annotations

from fpl_optimizer.database.base import Database
from fpl_optimizer.database.change_repository import (
    ChangeRepository,
    ForecastState,
    MarketState,
    OfficialState,
)
from fpl_optimizer.domain.changes import ChangeReport, ChangeWindow, PlayerChange


class ChangeDetectionService:
    """Compare immutable cached observations without rerunning any model."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def report(
        self,
        market_weight: float = 0.3,
        watchlist_ids: frozenset[int] = frozenset(),
    ) -> ChangeReport:
        """Return material changes between the latest two observations per source."""

        if not 0.0 <= market_weight <= 1.0:
            raise ValueError("Market weight must be between 0 and 1")
        with self.database.session() as session:
            repository = ChangeRepository(session)
            identities = repository.identities()
            official = repository.official_states()
            forecast = repository.forecast_states()
            market = repository.market_states()

        changes: list[PlayerChange] = []
        for player_id, identity in identities.items():
            change = _player_change(
                player_id=player_id,
                full_name=identity.full_name,
                team=identity.team,
                position=identity.position,
                watchlisted=player_id in watchlist_ids,
                current_official=official.current.get(player_id),
                previous_official=official.previous.get(player_id),
                current_forecast=forecast.current.get(player_id),
                previous_forecast=forecast.previous.get(player_id),
                current_market=market.current.get(player_id),
                previous_market=market.previous.get(player_id),
                market_weight=market_weight,
            )
            if change.change_types:
                changes.append(change)

        changes.sort(key=lambda item: (-item.significance, item.full_name))
        return ChangeReport(
            changes=tuple(changes),
            windows=(
                ChangeWindow("Official FPL", official.previous_at, official.current_at),
                ChangeWindow("Statistical forecast", forecast.previous_at, forecast.current_at),
                ChangeWindow("Market forecast", market.previous_at, market.current_at),
            ),
        )


def _player_change(
    *,
    player_id: int,
    full_name: str,
    team: str,
    position: str,
    watchlisted: bool,
    current_official: OfficialState | None,
    previous_official: OfficialState | None,
    current_forecast: ForecastState | None,
    previous_forecast: ForecastState | None,
    current_market: MarketState | None,
    previous_market: MarketState | None,
    market_weight: float,
) -> PlayerChange:
    price_delta = _state_delta(current_official, previous_official, "price")
    ownership_delta = _state_delta(current_official, previous_official, "ownership")
    minutes_delta = _state_delta(current_forecast, previous_forecast, "expected_minutes")
    market_delta = _state_delta(current_market, previous_market, "xpts")
    goal_probability_delta = _state_delta(
        current_market, previous_market, "goal_probability"
    )

    current_blended, previous_blended = _paired_blend(
        current_forecast,
        previous_forecast,
        current_market,
        previous_market,
        "xpts",
        market_weight,
    )
    current_3gw, previous_3gw = _paired_blend(
        current_forecast,
        previous_forecast,
        current_market,
        previous_market,
        "xpts_3gw",
        market_weight,
    )
    current_5gw, previous_5gw = _paired_blend(
        current_forecast,
        previous_forecast,
        current_market,
        previous_market,
        "xpts_5gw",
        market_weight,
    )
    blended_delta = _delta(current_blended, previous_blended)
    xpts_3gw_delta = _delta(current_3gw, previous_3gw)
    xpts_5gw_delta = _delta(current_5gw, previous_5gw)

    availability_changed = bool(
        current_official
        and previous_official
        and previous_official.status
        and (
            current_official.status != previous_official.status
            or current_official.chance_next_round != previous_official.chance_next_round
        )
    )
    news_changed = bool(
        current_official
        and previous_official
        and previous_official.status
        and current_official.news != previous_official.news
    )
    types: list[str] = []
    if _material(blended_delta, 0.05) or _material(xpts_5gw_delta, 0.1):
        types.append("xPts")
    if _material(minutes_delta, 0.5):
        types.append("Minutes")
    if _material(price_delta, 0.05):
        types.append("Price")
    if _material(ownership_delta, 0.05):
        types.append("Ownership")
    if _material(market_delta, 0.05) or _material(goal_probability_delta, 0.005):
        types.append("Market")
    if availability_changed:
        types.append("Availability")
    if news_changed:
        types.append("News")

    significance = (
        abs(blended_delta or 0.0) * 20.0
        + abs(xpts_5gw_delta or 0.0) * 4.0
        + abs(minutes_delta or 0.0) / 2.0
        + abs(price_delta or 0.0) * 20.0
        + abs(ownership_delta or 0.0) * 2.0
        + abs(market_delta or 0.0) * 10.0
        + (25.0 if availability_changed else 0.0)
        + (5.0 if news_changed else 0.0)
    )
    return PlayerChange(
        player_id=player_id,
        full_name=full_name,
        team=team,
        position=position,
        watchlisted=watchlisted,
        price=current_official.price if current_official else None,
        price_delta=price_delta,
        ownership=current_official.ownership if current_official else None,
        ownership_delta=ownership_delta,
        expected_minutes=current_forecast.expected_minutes if current_forecast else None,
        expected_minutes_delta=minutes_delta,
        blended_xpts=current_blended,
        blended_xpts_delta=blended_delta,
        xpts_3gw=current_3gw,
        xpts_3gw_delta=xpts_3gw_delta,
        xpts_5gw=current_5gw,
        xpts_5gw_delta=xpts_5gw_delta,
        market_xpts=current_market.xpts if current_market else None,
        market_xpts_delta=market_delta,
        goal_probability=current_market.goal_probability if current_market else None,
        goal_probability_delta=goal_probability_delta,
        status_before=previous_official.status if previous_official else None,
        status=current_official.status if current_official else None,
        news_before=previous_official.news if previous_official else None,
        news=current_official.news if current_official else None,
        chance_next_round=current_official.chance_next_round if current_official else None,
        change_types=tuple(types),
        significance=significance,
    )


def _state_delta(current: object | None, previous: object | None, field: str) -> float | None:
    if current is None or previous is None:
        return None
    return _delta(getattr(current, field), getattr(previous, field))


def _delta(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return current - previous


def _paired_blend(
    current_forecast: ForecastState | None,
    previous_forecast: ForecastState | None,
    current_market: MarketState | None,
    previous_market: MarketState | None,
    field: str,
    market_weight: float,
) -> tuple[float | None, float | None]:
    if current_forecast is None or previous_forecast is None:
        return None, None
    current_stat = float(getattr(current_forecast, field))
    previous_stat = float(getattr(previous_forecast, field))
    if current_market is None or previous_market is None:
        return current_stat, previous_stat
    return (
        current_stat * (1.0 - market_weight)
        + float(getattr(current_market, field)) * market_weight,
        previous_stat * (1.0 - market_weight)
        + float(getattr(previous_market, field)) * market_weight,
    )


def _material(value: float | None, threshold: float) -> bool:
    return value is not None and abs(value) >= threshold
