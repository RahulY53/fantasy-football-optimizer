"""Searchable current FPL player browser."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from shared import (
    load_forecast_summaries,
    load_players,
    load_strategy_scores,
    page_setup,
    require_data,
)

container = page_setup("Players", "👤")
st.title("Players")
st.caption("Official FPL data with current six-Gameweek statistical projections")
market_status = container.live_odds.status()
if market_status.last_sync is not None:
    label = "STALE ODDS" if market_status.stale else "Market data current"
    st.caption(f"{label} · odds updated {market_status.last_sync:%d %b, %H:%M}")
else:
    st.caption("Market forecast unavailable · blended xPts falls back to statistical xPts")

rows = load_players(container)
if require_data(rows, "players"):
    frame = pd.DataFrame(rows)
    forecasts = pd.DataFrame(load_forecast_summaries(container))
    if not forecasts.empty:
        frame = frame.merge(forecasts, on="Player ID", how="left")
        scores = pd.DataFrame(load_strategy_scores(container))
        if not scores.empty:
            frame = frame.merge(scores, on="Player ID", how="left")
    else:
        st.info("Generate statistical forecasts from the sidebar to add expected minutes and xPts.")
    filter_cols = st.columns([2, 1, 1, 1])
    search = filter_cols[0].text_input("Search", placeholder="Player name")
    positions = filter_cols[1].multiselect(
        "Position", options=sorted(frame["Position"].dropna().unique())
    )
    teams = filter_cols[2].multiselect("Team", options=sorted(frame["Team"].dropna().unique()))
    available_only = filter_cols[3].toggle("Available only", value=False)

    filtered = frame
    if search:
        filtered = filtered[
            filtered["Player"].str.contains(search, case=False, regex=False, na=False)
        ]
    if positions:
        filtered = filtered[filtered["Position"].isin(positions)]
    if teams:
        filtered = filtered[filtered["Team"].isin(teams)]
    if available_only:
        filtered = filtered[filtered["Status"] == "a"]

    st.write(f"{len(filtered)} of {len(frame)} players")
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
            "6GW xPts": st.column_config.NumberColumn("6GW xPts", format="%.1f"),
            "Value": st.column_config.NumberColumn("Value", format="%.1f"),
            "Risk": st.column_config.NumberColumn("Risk", format="%.0f/100"),
            "Optimization Score": st.column_config.ProgressColumn(
                "Optimization", min_value=0, max_value=100, format="%.1f"
            ),
            "Updated": st.column_config.DatetimeColumn("Updated", format="DD MMM, HH:mm"),
        },
        column_order=(
            "Player",
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
            "Ownership %",
            "Form",
            "Points/game",
            "Status",
            "News",
            "Updated",
        ),
    )
