"""Reusable combined player filters for tables and analytics charts."""

from __future__ import annotations

import streamlit as st

from fpl_optimizer.analytics.filters import PlayerFilterSpec
from fpl_optimizer.analytics.player_dataset import PlayerAnalyticsRecord


def render_player_filters(
    records: tuple[PlayerAnalyticsRecord, ...], key_prefix: str = "players"
) -> PlayerFilterSpec:
    """Render shared basic and advanced controls and return serializable state."""

    teams = sorted({record.team for record in records})
    positions = [
        position
        for position in ("GK", "DEF", "MID", "FWD")
        if any(record.position == position for record in records)
    ]
    columns = st.columns([2, 1, 1, 1])
    search = columns[0].text_input(
        "Search",
        placeholder="First name, surname, or FPL web name",
        key=f"{key_prefix}_search",
    )
    selected_positions = columns[1].multiselect(
        "Position", positions, key=f"{key_prefix}_positions"
    )
    selected_teams = columns[2].multiselect("Team", teams, key=f"{key_prefix}_teams")
    available_only = columns[3].toggle("Available only", value=False, key=f"{key_prefix}_available")

    prices = [record.price for record in records]
    ownership = [record.ownership for record in records]
    minimum_price = _floor(min(prices), 0.5)
    maximum_price = max(_ceil(max(prices), 0.5), minimum_price + 0.5)
    with st.expander("Advanced filters"):
        row_one = st.columns(4)
        price_range = row_one[0].slider(
            "Price range",
            min_value=minimum_price,
            max_value=maximum_price,
            value=(minimum_price, maximum_price),
            step=0.5,
            format="£%.1fm",
            key=f"{key_prefix}_price",
        )
        ownership_range = row_one[1].slider(
            "Ownership range",
            min_value=0.0,
            max_value=max(100.0, _ceil(max(ownership), 1.0)),
            value=(0.0, max(100.0, _ceil(max(ownership), 1.0))),
            step=1.0,
            format="%.0f%%",
            key=f"{key_prefix}_ownership",
        )
        minimum_minutes = _optional_threshold(
            row_one[2], "Minimum expected minutes", records, "expected_minutes", 5.0, key_prefix
        )
        minimum_next_xpts = _optional_threshold(
            row_one[3], "Minimum next-GW xPts", records, "blended_xpts", 0.5, key_prefix
        )
        row_two = st.columns(4)
        minimum_3gw = _optional_threshold(
            row_two[0], "Minimum 3GW xPts", records, "xpts_3gw", 1.0, key_prefix
        )
        minimum_5gw = _optional_threshold(
            row_two[1], "Minimum 5GW xPts", records, "xpts_5gw", 1.0, key_prefix
        )
        maximum_risk = _optional_ceiling(
            row_two[2], "Maximum risk", records, "risk", 5.0, key_prefix
        )
        minimum_score = _optional_threshold(
            row_two[3],
            "Minimum optimization score",
            records,
            "optimization_score",
            5.0,
            key_prefix,
        )

    return PlayerFilterSpec(
        search=search,
        teams=tuple(selected_teams),
        positions=tuple(selected_positions),
        price_range=price_range,
        ownership_range=ownership_range,
        minimum_expected_minutes=minimum_minutes,
        minimum_blended_xpts=minimum_next_xpts,
        minimum_xpts_3gw=minimum_3gw,
        minimum_xpts_5gw=minimum_5gw,
        maximum_risk=maximum_risk,
        minimum_optimization_score=minimum_score,
        available_only=available_only,
    )


def _optional_threshold(
    column: object,
    label: str,
    records: tuple[PlayerAnalyticsRecord, ...],
    attribute: str,
    step: float,
    key_prefix: str,
) -> float | None:
    values = _values(records, attribute)
    if not values:
        column.caption(f"{label}: generate forecasts first")  # type: ignore[attr-defined]
        return None
    enabled = column.checkbox(  # type: ignore[attr-defined]
        label, value=False, key=f"{key_prefix}_{attribute}_enabled"
    )
    threshold = column.slider(  # type: ignore[attr-defined]
        f"{label} value",
        min_value=0.0,
        max_value=max(step, _ceil(max(values), step)),
        value=0.0,
        step=step,
        disabled=not enabled,
        key=f"{key_prefix}_{attribute}_minimum",
        label_visibility="collapsed",
    )
    return threshold if enabled else None


def _optional_ceiling(
    column: object,
    label: str,
    records: tuple[PlayerAnalyticsRecord, ...],
    attribute: str,
    step: float,
    key_prefix: str,
) -> float | None:
    values = _values(records, attribute)
    if not values:
        column.caption(f"{label}: generate forecasts first")  # type: ignore[attr-defined]
        return None
    maximum = max(step, _ceil(max(values), step))
    enabled = column.checkbox(  # type: ignore[attr-defined]
        label, value=False, key=f"{key_prefix}_{attribute}_enabled"
    )
    threshold = column.slider(  # type: ignore[attr-defined]
        f"{label} value",
        min_value=0.0,
        max_value=maximum,
        value=maximum,
        step=step,
        disabled=not enabled,
        key=f"{key_prefix}_{attribute}_maximum",
        label_visibility="collapsed",
    )
    return threshold if enabled else None


def _values(records: tuple[PlayerAnalyticsRecord, ...], attribute: str) -> list[float]:
    return [float(value) for record in records if (value := getattr(record, attribute)) is not None]


def _floor(value: float, step: float) -> float:
    return int(value / step) * step


def _ceil(value: float, step: float) -> float:
    return int((value + step - 1e-9) / step) * step
