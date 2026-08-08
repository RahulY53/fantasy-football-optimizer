"""Composable filters shared by player tables and visual analytics."""

from __future__ import annotations

from dataclasses import dataclass

from fpl_optimizer.analytics.player_dataset import PlayerAnalyticsRecord
from fpl_optimizer.domain.names import normalize_name_query


@dataclass(frozen=True, slots=True)
class PlayerFilterSpec:
    """Serializable filter state that can be shared across analytics views."""

    search: str = ""
    teams: tuple[str, ...] = ()
    positions: tuple[str, ...] = ()
    price_range: tuple[float, float] | None = None
    ownership_range: tuple[float, float] | None = None
    minimum_expected_minutes: float | None = None
    minimum_blended_xpts: float | None = None
    minimum_xpts_3gw: float | None = None
    minimum_xpts_5gw: float | None = None
    maximum_risk: float | None = None
    minimum_optimization_score: float | None = None
    available_only: bool = False
    watchlist_only: bool = False
    watchlist_ids: frozenset[int] = frozenset()


def filter_players(
    records: tuple[PlayerAnalyticsRecord, ...] | list[PlayerAnalyticsRecord],
    filters: PlayerFilterSpec,
) -> tuple[PlayerAnalyticsRecord, ...]:
    """Apply all selected filters together without recalculating forecasts."""

    query = normalize_name_query(filters.search)
    return tuple(
        record
        for record in records
        if (not query or query in record.name_search)
        and (not filters.teams or record.team in filters.teams)
        and (not filters.positions or record.position in filters.positions)
        and _between(record.price, filters.price_range)
        and _between(record.ownership, filters.ownership_range)
        and _minimum(record.expected_minutes, filters.minimum_expected_minutes)
        and _minimum(record.blended_xpts, filters.minimum_blended_xpts)
        and _minimum(record.xpts_3gw, filters.minimum_xpts_3gw)
        and _minimum(record.xpts_5gw, filters.minimum_xpts_5gw)
        and _maximum(record.risk, filters.maximum_risk)
        and _minimum(record.optimization_score, filters.minimum_optimization_score)
        and (not filters.available_only or record.status == "a")
        and (not filters.watchlist_only or record.player_id in filters.watchlist_ids)
    )


def _between(value: float, bounds: tuple[float, float] | None) -> bool:
    return bounds is None or bounds[0] <= value <= bounds[1]


def _minimum(value: float | None, threshold: float | None) -> bool:
    return threshold is None or (value is not None and value >= threshold)


def _maximum(value: float | None, threshold: float | None) -> bool:
    return threshold is None or (value is not None and value <= threshold)
