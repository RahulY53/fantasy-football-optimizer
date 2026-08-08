"""Gameweek-aware Premier League fixture browser."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from shared import load_fixtures, page_setup, require_data

container = page_setup("Fixtures", "📅")
st.title("Fixtures")
st.caption("Kickoff times, FPL difficulty, blanks, doubles, and completed scores")

rows = load_fixtures(container)
if require_data(rows, "fixtures"):
    frame = pd.DataFrame(rows)
    gameweek_options = list(dict.fromkeys(frame["Gameweek"].tolist()))
    selected_gameweeks = st.multiselect("Gameweek", gameweek_options)
    show_completed = st.toggle("Show completed fixtures", value=True)

    filtered = frame
    if selected_gameweeks:
        filtered = filtered[filtered["Gameweek"].isin(selected_gameweeks)]
    if not show_completed:
        filtered = filtered[filtered["Status"] != "finished"]

    st.write(f"{len(filtered)} fixtures")
    st.dataframe(
        filtered,
        hide_index=True,
        width="stretch",
        column_config={
            "Kickoff": st.column_config.DatetimeColumn(
                "Kickoff (your timezone)", format="ddd DD MMM, HH:mm"
            ),
            "Home difficulty": st.column_config.ProgressColumn(
                "Home FDR", min_value=1, max_value=5, format="%d"
            ),
            "Away difficulty": st.column_config.ProgressColumn(
                "Away FDR", min_value=1, max_value=5, format="%d"
            ),
        },
    )

    counts = frame.groupby("Gameweek", sort=False).size()
    doubles = counts[counts > 10]
    if not doubles.empty:
        st.info(
            "Potential double Gameweeks detected by fixture count: "
            + ", ".join(f"{name} ({count} fixtures)" for name, count in doubles.items())
        )
