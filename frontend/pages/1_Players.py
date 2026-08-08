"""Searchable current FPL player browser."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from components.player_filters import render_player_filters
from shared import (
    load_player_analytics,
    page_setup,
    require_data,
)

from fpl_optimizer.analytics.filters import filter_players

container = page_setup("Players", "👤")
st.title("Players")
st.caption("Official FPL data with current six-Gameweek statistical projections")
market_status = container.live_odds.status()
if market_status.last_sync is not None:
    label = "STALE ODDS" if market_status.stale else "Market data current"
    st.caption(f"{label} · odds updated {market_status.last_sync:%d %b, %H:%M}")
else:
    st.caption("Market forecast unavailable · blended xPts falls back to statistical xPts")

records = load_player_analytics(container)
if require_data(list(records), "players"):
    if not any(record.blended_xpts is not None for record in records):
        st.info("Generate statistical forecasts from the sidebar to add expected minutes and xPts.")
    filters = render_player_filters(records)
    filtered_records = filter_players(records, filters)
    frame = pd.DataFrame(record.as_row() for record in records)
    filtered_ids = {record.player_id for record in filtered_records}
    filtered = frame[frame["Player ID"].isin(filtered_ids)]

    st.write(f"{len(filtered_records)} of {len(records)} players")
    st.dataframe(
        filtered,
        hide_index=True,
        width="stretch",
        column_config={
            "Price": st.column_config.NumberColumn("Price", format="£%.1fm"),
            "Ownership %": st.column_config.NumberColumn("Ownership", format="%.1f%%"),
            "Form": st.column_config.NumberColumn("Form", format="%.1f"),
            "Points/game": st.column_config.NumberColumn("Pts/game", format="%.1f"),
            "Expected minutes": st.column_config.NumberColumn("xMins", format="%.0f"),
            "Stat xPts": st.column_config.NumberColumn("Stat xPts", format="%.1f"),
            "Market xPts": st.column_config.NumberColumn("Market xPts", format="%.1f"),
            "Blended xPts": st.column_config.NumberColumn("Blended xPts", format="%.1f"),
            "Market edge": st.column_config.NumberColumn("Market edge", format="%+.1f"),
            "3GW xPts": st.column_config.NumberColumn("3GW xPts", format="%.1f"),
            "5GW xPts": st.column_config.NumberColumn("5GW xPts", format="%.1f"),
            "6GW xPts": st.column_config.NumberColumn("6GW xPts", format="%.1f"),
            "Value": st.column_config.NumberColumn("Value", format="%.1f"),
            "Risk": st.column_config.NumberColumn("Risk", format="%.0f/100"),
            "Optimization Score": st.column_config.ProgressColumn(
                "Optimization", min_value=0, max_value=100, format="%.1f"
            ),
            "Updated": st.column_config.DatetimeColumn("Updated", format="DD MMM, HH:mm"),
        },
        column_order=(
            "Full Name",
            "Position",
            "Team",
            "Price",
            "Opponent",
            "Expected minutes",
            "Stat xPts",
            "Market xPts",
            "Blended xPts",
            "Market edge",
            "3GW xPts",
            "5GW xPts",
            "6GW xPts",
            "Value",
            "Risk",
            "Optimization Score",
            "Forecast confidence",
            "Points",
            "Minutes",
            "Starts",
            "Goals",
            "Assists",
            "Clean sheets",
            "Defensive contributions",
            "CBI",
            "Tackles",
            "Recoveries",
            "Ownership %",
            "Form",
            "Points/game",
            "Status",
            "News",
            "Updated",
        ),
    )
